import type { CategoryTag } from "@/lib/types";

// Exact values from BursaTrack.dc.html's tagColors computation:
// Dividend -> ['#E7F5EE', '#177A4E'], Growth -> ['#EBF0FF', '#2B3EB8'],
// Volatile (else) -> ['#F0F0ED', '#5D6069']. Growth's colors equal the
// --secondary/--secondary-foreground tokens; Volatile's equal
// --muted/--muted-foreground — mapped to those tokens rather than
// duplicating the hex values.
export const CATEGORY_TAG_STYLES: Record<CategoryTag, string> = {
  Dividend: "bg-[#E7F5EE] text-[#177A4E]",
  Growth: "bg-secondary text-secondary-foreground",
  Volatile: "bg-muted text-muted-foreground",
};
