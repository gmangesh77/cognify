"use client";

import { useRouter } from "next/navigation";
import { SavedAssetGallery } from "@/components/visuals/SavedAssetGallery";

/**
 * Top-level "My visuals" page (Phase 7 / VISUAL-010).
 *
 * Reuses `SavedAssetGallery` as a full-screen view: the editor lands
 * directly inside the gallery, so the modal's close affordance routes
 * back to `/articles` as the obvious "out" for a top-level page.
 *
 * Editors typically reach this from the sidebar nav. The article-detail
 * page mounts the same component as a dismissible modal for the
 * pick-and-insert workflow.
 */
export default function SavedVisualsPage() {
  const router = useRouter();
  return (
    <SavedAssetGallery
      open
      onClose={() => router.push("/articles")}
    />
  );
}
