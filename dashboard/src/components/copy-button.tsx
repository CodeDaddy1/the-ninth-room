"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

export function CopyButton({
  text,
  label = "Copy",
  variant = "default",
  className,
}: {
  text: string;
  label?: string;
  variant?: "default" | "secondary" | "outline" | "ghost";
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // No clipboard permission — surface nothing; users can select+copy manually.
    }
  };

  return (
    <Button
      type="button"
      variant={variant}
      size="sm"
      onClick={onClick}
      className={cn("gap-2", className)}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {copied ? "Copied" : label}
    </Button>
  );
}
