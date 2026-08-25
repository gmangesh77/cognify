import { Button } from "@/components/ui/button";
import type { OutlineSection } from "@/types/research";

interface OutlineSectionEditorProps {
  section: OutlineSection;
  index: number;
  total: number;
  onChange: (section: OutlineSection) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDelete: () => void;
}

/** One editable row within OutlineReviewStep's section list — title,
 * key points (one per line), reorder, and delete. Kept as a separate
 * component so both files stay under the 200-line project limit. */
export function OutlineSectionEditor({
  section,
  index,
  total,
  onChange,
  onMoveUp,
  onMoveDown,
  onDelete,
}: OutlineSectionEditorProps) {
  return (
    <div role="listitem" className="space-y-2 rounded-md border border-neutral-200 p-3">
      <div className="flex items-center justify-between gap-2">
        <input
          aria-label={`Section ${index + 1} title`}
          value={section.title}
          onChange={(e) => onChange({ ...section, title: e.target.value })}
          className="flex-1 rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
        />
        <span className="shrink-0 text-xs font-medium text-neutral-500">
          ~{section.target_word_count} words
        </span>
        <div className="flex shrink-0 gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Move section ${index + 1} up`}
            onClick={onMoveUp}
            disabled={index === 0}
          >
            ↑
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Move section ${index + 1} down`}
            onClick={onMoveDown}
            disabled={index === total - 1}
          >
            ↓
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Delete section ${index + 1}`}
            onClick={onDelete}
          >
            Delete
          </Button>
        </div>
      </div>
      <textarea
        aria-label={`Section ${index + 1} key points`}
        value={section.key_points.join("\n")}
        onChange={(e) =>
          onChange({
            ...section,
            key_points: e.target.value
              .split("\n")
              .map((line) => line.trim())
              .filter((line) => line.length > 0),
          })
        }
        rows={3}
        placeholder="One key point per line"
        className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
      />
    </div>
  );
}
