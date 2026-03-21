import { useState } from "react";
import { Button } from "@/components/ui/button";

const PLATFORMS = [
  { value: "ghost", label: "Ghost" },
  { value: "wordpress", label: "WordPress" },
  { value: "medium", label: "Medium" },
  { value: "linkedin", label: "LinkedIn" },
];

interface PublishModalProps {
  open: boolean;
  onClose: () => void;
  onPublish: (platforms: string[]) => void;
}

export function PublishModal({ open, onClose, onPublish }: PublishModalProps) {
  const [selected, setSelected] = useState<string[]>([]);

  if (!open) return null;

  function toggle(platform: string) {
    setSelected((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform],
    );
  }

  function handlePublish() {
    onPublish(selected);
    setSelected([]);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        role="dialog"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          Publish Article
        </h2>
        <p className="mt-1 text-sm text-neutral-500">
          Select platforms to publish this article to.
        </p>

        <div className="mt-4 space-y-3">
          {PLATFORMS.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selected.includes(value)}
                onChange={() => toggle(value)}
                className="rounded"
                aria-label={label}
              />
              {label}
            </label>
          ))}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={selected.length === 0} onClick={handlePublish}>
            Publish
          </Button>
        </div>
      </div>
    </div>
  );
}
