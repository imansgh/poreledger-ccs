import type { InputLabel } from "@/lib/types";

const CLASS: Record<InputLabel, string> = {
  source: "tag tag-source",
  MODELLED: "tag tag-modelled",
  ASSUMED: "tag tag-assumed",
  USER: "tag tag-user",
};

const TEXT: Record<InputLabel, string> = {
  source: "SOURCE",
  MODELLED: "MODELLED",
  ASSUMED: "ASSUMED",
  USER: "USER INPUT",
};

/**
 * Provenance badge. The label is always spelled out in text: colour alone must
 * never be what tells a reader an input was assumed rather than measured.
 */
export function Tag({ label }: { label: InputLabel }) {
  return <span className={CLASS[label]}>{TEXT[label]}</span>;
}
