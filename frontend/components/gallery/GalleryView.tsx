"use client";

import { useState } from "react";
import { useSelector, useDispatch } from "react-redux";
import { RootState } from "@/store/store";
import { updateSlideStatus } from "@/store/pipelineSlice";
import { SlideThumbnail } from "./SlideThumbnail";
import { SlidePreview } from "./SlidePreview";
import { NarrativePanel } from "./NarrativePanel";
import { api } from "@/lib/api";

export function GalleryView() {
  const { pipelineId, slides, narrativeSuggestions } = useSelector(
    (state: RootState) => state.pipeline
  );
  const dispatch = useDispatch();
  const [activeIndex, setActiveIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirmedCount = slides.filter((s) => s.status === "confirmed").length;
  const flaggedCount = slides.filter((s) => s.status === "flagged").length;

  const handleConfirmSlide = (index: number) => {
    dispatch(updateSlideStatus({ index, status: "confirmed" }));
  };

  const handleFlagSlide = (index: number, feedback: string) => {
    dispatch(updateSlideStatus({ index, status: "flagged", feedback }));
  };

  const handleConfirmAll = async () => {
    if (!pipelineId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const flaggedIndices = slides
        .filter((s) => s.status === "flagged")
        .map((s) => s.index);
      await api.confirmNode(pipelineId, {
        node: "hitl_gallery",
        action: "confirm",
        flagged_indices: flaggedIndices,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to confirm gallery");
      setSubmitting(false);
    }
    // Don't reset submitting on success — pipeline is now running, page will update
  };

  return (
    <div className="flex h-full flex-col">
      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Thumbnails */}
        <div className="w-48 border-r overflow-y-auto p-2 space-y-2">
          {slides.map((slide) => (
            <SlideThumbnail
              key={slide.index}
              slide={slide}
              isActive={slide.index === activeIndex}
              onClick={() => setActiveIndex(slide.index)}
            />
          ))}
        </div>

        {/* Right: Preview + Narrative */}
        <div className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto p-6">
            {slides[activeIndex] && (
              <SlidePreview
                slide={slides[activeIndex]}
                onConfirm={() => handleConfirmSlide(activeIndex)}
                onFlag={(feedback) => handleFlagSlide(activeIndex, feedback)}
              />
            )}
          </div>

          {narrativeSuggestions.length > 0 && (
            <NarrativePanel suggestions={narrativeSuggestions} />
          )}
        </div>
      </div>

      {/* Bottom: Progress + Actions */}
      <div className="border-t p-4 flex items-center justify-between">
        <span className="text-sm text-gray-600">
          {confirmedCount}/{slides.length} confirmed
          {flaggedCount > 0 && `, ${flaggedCount} flagged`}
        </span>
        <button
          onClick={handleConfirmAll}
          disabled={submitting}
          className="px-4 py-2 bg-green-600 text-white rounded font-medium disabled:opacity-50"
        >
          {submitting ? "Generating PPT…" : "Confirm all, generate PPT"}
        </button>
      </div>
    </div>
  );
}
