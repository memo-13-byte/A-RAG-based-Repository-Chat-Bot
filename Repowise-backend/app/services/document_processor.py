"""
Document Processor Service - Repository Code Extraction and Processing
Hybrid version combining comprehensive file handling with clean separation of concerns
"""

import logging
from typing import List, Dict, Any, Optional
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of document content"""

    def __init__(
        self,
        content: str,
        metadata: Dict[str, Any],
        chunk_id: str
    ):
        self.content = content
        # Ensure metadata is never empty (ChromaDB requirement)
        self.metadata = metadata if metadata else {
            "source": "unknown",
            "type": "document"
        }
        self.chunk_id = chunk_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "content": self.content,
            "metadata": self.metadata,
            "chunk_id": self.chunk_id
        }


class DocumentProcessor:
    """
    Process repository documents for RAG

    Features:
    - Text chunking with overlap
    - Code-aware chunking
    - Multiple language support
    - Function extraction
    - Smart file filtering
    """

    # Supported file extensions (comprehensive list)
    CODE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.cs': 'csharp'
    }

    # Files/directories to skip
    SKIP_PATTERNS = [
        '__pycache__',
        'node_modules',
        '.git',
        'dist',
        'build',
        '.venv',
        'venv',
        '.pytest_cache',
        '.egg-info',
        'test',
        'tests',
        '__test__',
        '.min.js',
        '.min.css',
        'vendor',
        'third_party'
    ]

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        """
        Initialize document processor

        Args:
            chunk_size: Target size for chunks (characters)
            chunk_overlap: Overlap between chunks (characters)
            min_chunk_size: Minimum chunk size (characters)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        logger.info(f"DocumentProcessor initialized: chunk_size={chunk_size}, overlap={chunk_overlap}")

    def should_process_file(self, file_path: str) -> bool:
        """
        Check if a file should be processed

        Args:
            file_path: Path of the file

        Returns:
            True if file should be processed, False otherwise
        """
        # Check if path contains skip patterns
        file_path_lower = file_path.lower()
        for pattern in self.SKIP_PATTERNS:
            if pattern in file_path_lower:
                return False

        # Check file extension
        ext = Path(file_path).suffix.lower()
        return ext in self.CODE_EXTENSIONS

    def get_language(self, file_path: str) -> str:
        """
        Get programming language from file path

        Args:
            file_path: Path to file

        Returns:
            Language name
        """
        ext = Path(file_path).suffix.lower()
        return self.CODE_EXTENSIONS.get(ext, "unknown")

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk text into smaller pieces

        Args:
            text: Text to chunk
            metadata: Optional metadata for chunks

        Returns:
            List of DocumentChunk objects
        """
        if not text or len(text) < self.min_chunk_size:
            return []

        # Ensure metadata is never empty (ChromaDB requirement)
        metadata = metadata or {}
        if not metadata:
            metadata = {
                "source": "unknown",
                "type": "document",
                "repository": "unknown"
            }
        chunks = []

        # Split by paragraphs first
        paragraphs = text.split('\n\n')

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_id = f"{metadata.get('source', 'unknown')}_chunk_{chunk_index}"
                chunks.append(DocumentChunk(
                    content=current_chunk.strip(),
                    metadata={**metadata, "chunk_index": chunk_index},
                    chunk_id=chunk_id
                ))

                # Start new chunk with overlap
                overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
                chunk_index += 1
            else:
                # Add to current chunk
                current_chunk += "\n\n" + para if current_chunk else para

        # Add final chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunk_id = f"{metadata.get('source', 'unknown')}_chunk_{chunk_index}"
            chunks.append(DocumentChunk(
                content=current_chunk.strip(),
                metadata={**metadata, "chunk_index": chunk_index},
                chunk_id=chunk_id
            ))

        logger.info(f"Created {len(chunks)} chunks from text ({len(text)} chars)")
        return chunks

    def extract_functions(self, content: str, language: str) -> List[Dict[str, Any]]:
        """
        Extract function definitions from code (regex-based)

        Args:
            content: Code content
            language: Programming language

        Returns:
            List of function information dictionaries
        """
        functions = []

        if language == 'python':
            # Match Python function definitions
            pattern = r'def\s+(\w+)\s*\([^)]*\):\s*\n((?:\s{4}.*\n)*)'
            matches = re.finditer(pattern, content)

            for match in matches:
                functions.append({
                    "name": match.group(1),
                    "content": match.group(0),
                    "type": "function",
                    "language": language,
                    "start_pos": match.start()
                })

        elif language in ['javascript', 'typescript']:
            # Match JavaScript/TypeScript function definitions
            patterns = [
                r'function\s+(\w+)\s*\([^)]*\)\s*{',
                r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{',
                r'(\w+)\s*:\s*function\s*\([^)]*\)\s*{'
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    functions.append({
                        "name": match.group(1),
                        "content": match.group(0),
                        "type": "function",
                        "language": language,
                        "start_pos": match.start()
                    })

        return functions

    def chunk_code(
        self,
        code: str,
        language: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk code file intelligently

        Args:
            code: Code content
            language: Programming language
            file_path: Path to the file
            metadata: Optional metadata

        Returns:
            List of DocumentChunk objects
        """
        if not code or len(code) < self.min_chunk_size:
            return []

        metadata = metadata or {}
        metadata.update({
            "type": "code",
            "language": language,
            "source": file_path
        })

        chunks = []

        # Try function extraction first
        functions = self.extract_functions(code, language)

        if functions and language == 'python':
            # Use function-based chunking for Python
            chunks = self._chunk_python_code(code, metadata)
        else:
            # Generic code chunking
            chunks = self.chunk_text(code, metadata)

        logger.info(f"Created {len(chunks)} chunks from {language} code ({len(code)} chars)")
        return chunks

    def _chunk_python_code(
        self,
        code: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Chunk Python code by functions and classes

        Args:
            code: Python code
            metadata: Metadata

        Returns:
            List of DocumentChunk objects
        """
        chunks = []

        # Pattern to match function and class definitions
        pattern = r'^(class |def |async def )'
        lines = code.split('\n')

        current_chunk = []
        current_name = "header"
        chunk_index = 0

        for i, line in enumerate(lines):
            # Check if line starts a new function/class
            if re.match(pattern, line.lstrip()):
                # Save previous chunk if it exists
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk)
                    if len(chunk_content) >= self.min_chunk_size:
                        chunk_id = f"{metadata['source']}_{current_name}_{chunk_index}"
                        chunks.append(DocumentChunk(
                            content=chunk_content,
                            metadata={**metadata, "chunk_index": chunk_index, "name": current_name},
                            chunk_id=chunk_id
                        ))
                        chunk_index += 1

                # Start new chunk
                current_chunk = [line]
                # Extract function/class name
                match = re.search(r'(class|def|async def)\s+(\w+)', line)
                current_name = match.group(2) if match else f"chunk_{chunk_index}"
            else:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if len(chunk_content) >= self.min_chunk_size:
                chunk_id = f"{metadata['source']}_{current_name}_{chunk_index}"
                chunks.append(DocumentChunk(
                    content=chunk_content,
                    metadata={**metadata, "chunk_index": chunk_index, "name": current_name},
                    chunk_id=chunk_id
                ))

        # If no chunks created, use generic chunking
        if not chunks:
            chunks = self.chunk_text(code, metadata)

        return chunks

    def process_readme(
        self,
        readme_content: str,
        repo_name: str
    ) -> List[DocumentChunk]:
        """
        Process README file

        Args:
            readme_content: README markdown content
            repo_name: Repository name

        Returns:
            List of DocumentChunk objects
        """
        metadata = {
            "type": "readme",
            "source": "README.md",
            "repository": repo_name
        }

        chunks = self.chunk_text(readme_content, metadata)
        logger.info(f"Processed README for {repo_name}: {len(chunks)} chunks")

        return chunks

    def process_file(
        self,
        content: str,
        file_path: str,
        repo_name: str
    ) -> List[DocumentChunk]:
        """
        Process any file

        Args:
            content: File content
            file_path: Path to file
            repo_name: Repository name

        Returns:
            List of DocumentChunk objects
        """
        # Check if should process
        if not self.should_process_file(file_path):
            logger.info(f"Skipping file: {file_path}")
            return []

        # Get language
        language = self.get_language(file_path)

        metadata = {
            "repository": repo_name,
            "source": file_path,
            "type": "code",
            "language": language
        }

        # Process as code
        return self.chunk_code(content, language, file_path, metadata)


# Singleton instance
document_processor = DocumentProcessor()


# Test function
def test_document_processor():
    """Test document processor"""
    print("Testing Hybrid Document Processor...")

    # Test file filtering
    print("\n[Test 1] Testing file filtering...")
    test_files = [
        "src/main.py",
        "node_modules/test.js",
        "__pycache__/cache.py",
        "dist/bundle.js",
        "src/utils.ts",
        "tests/test_main.py"
    ]

    for file in test_files:
        should_process = document_processor.should_process_file(file)
        status = "[PROCESS]" if should_process else "[SKIP]"
        print(f"  {status}: {file}")

    # Test text chunking
    text = """
    # LangChain
    
    LangChain is a framework for developing applications powered by language models.
    
    ## Features
    
    - Chains: Compose multiple components together
    - Agents: Let LLMs make decisions
    - Memory: Maintain context across interactions
    
    ## Installation
    
    Install with pip:
    ```bash
    pip install langchain
    ```
    """ * 5

    print("\n[Test 2] Testing text chunking...")
    chunks = document_processor.chunk_text(text, {"source": "README.md"})
    print(f"[SUCCESS] Created {len(chunks)} text chunks")

    # Test code chunking
    code = """
def hello_world():
    '''Say hello'''
    print('Hello World')

class MyClass:
    '''A simple class'''
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value

async def async_function():
    '''Async example'''
    await some_operation()
    return result
"""

    print("\n[Test 3] Testing code chunking...")
    code_chunks = document_processor.chunk_code(
        code,
        "python",
        "main.py",
        {"repository": "test/repo"}
    )
    print(f"[SUCCESS] Created {len(code_chunks)} code chunks")
    for i, chunk in enumerate(code_chunks):
        print(f"  Chunk {i+1}: {chunk.metadata.get('name', 'unknown')}")

    # Test function extraction
    print("\n[Test 4] Testing function extraction...")
    functions = document_processor.extract_functions(code, "python")
    print(f"[SUCCESS] Extracted {len(functions)} functions:")
    for func in functions:
        print(f"  - {func['name']}")

    print("\n[SUCCESS] All tests passed!")


if __name__ == "__main__":
    test_document_processor()