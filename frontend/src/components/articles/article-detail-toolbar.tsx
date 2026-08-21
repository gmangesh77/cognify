export interface ArticleDetailToolbarProps {
  studioOpen: boolean;
  onOpenGallery: () => void;
  onOpenImport: () => void;
  onToggleStudio: () => void;
}

const SECONDARY_BUTTON =
  "rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200";

/** Saved visuals / Import image / Visual Studio toggle row above the article column. */
export function ArticleDetailToolbar({
  studioOpen,
  onOpenGallery,
  onOpenImport,
  onToggleStudio,
}: ArticleDetailToolbarProps) {
  return (
    <div className="mb-4 flex items-center justify-end gap-2">
      <button type="button" onClick={onOpenGallery} className={SECONDARY_BUTTON}>
        Saved visuals
      </button>
      <button type="button" onClick={onOpenImport} className={SECONDARY_BUTTON}>
        Import image
      </button>
      <button
        type="button"
        onClick={onToggleStudio}
        aria-pressed={studioOpen}
        className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90"
      >
        {studioOpen ? "Hide Visual Studio" : "Open Visual Studio"}
      </button>
    </div>
  );
}
