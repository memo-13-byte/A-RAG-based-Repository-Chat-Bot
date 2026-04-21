import * as React from "react";
import { cn } from "../../lib/utils";

const TooltipProvider = ({ children }) => {
  return <>{children}</>;
};

const TooltipContext = React.createContext(null);

const Tooltip = ({ children, open, defaultOpen = false, onOpenChange, delayDuration = 200 }) => {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);
  const actualOpen = open !== undefined ? open : isOpen;
  const timeoutRef = React.useRef(null);

  const handleOpenChange = (newOpen) => {
    setIsOpen(newOpen);
    onOpenChange?.(newOpen);
  };

  const handleMouseEnter = () => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => handleOpenChange(true), delayDuration);
  };

  const handleMouseLeave = () => {
    clearTimeout(timeoutRef.current);
    handleOpenChange(false);
  };

  return (
    <TooltipContext.Provider value={{ isOpen: actualOpen, handleMouseEnter, handleMouseLeave }}>
      {children}
    </TooltipContext.Provider>
  );
};

const TooltipTrigger = React.forwardRef(({ className, asChild, children, ...props }, ref) => {
  const context = React.useContext(TooltipContext);
  
  return (
    <span
      ref={ref}
      className={cn("inline-flex", className)}
      onMouseEnter={context?.handleMouseEnter}
      onMouseLeave={context?.handleMouseLeave}
      onFocus={context?.handleMouseEnter}
      onBlur={context?.handleMouseLeave}
      {...props}
    >
      {children}
    </span>
  );
});
TooltipTrigger.displayName = "TooltipTrigger";

const TooltipContent = React.forwardRef(
  ({ className, sideOffset = 4, children, ...props }, ref) => {
    const context = React.useContext(TooltipContext);

    if (!context?.isOpen) return null;

    return (
      <div
        ref={ref}
        className={cn(
          "z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95",
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);
TooltipContent.displayName = "TooltipContent";

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
