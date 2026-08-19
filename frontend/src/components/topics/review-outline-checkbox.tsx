interface ReviewOutlineCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/** "Review outline before drafting" opt-in, shared by GenerateArticleModal
 * and CreateTopicModal so the markup isn't duplicated between the two. */
export function ReviewOutlineCheckbox({ checked, onChange }: ReviewOutlineCheckboxProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-neutral-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-neutral-300 text-primary focus:ring-primary"
      />
      Review outline before drafting
    </label>
  );
}
