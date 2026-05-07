"use client";

import { useSelector, useDispatch } from "react-redux";
import { RootState } from "@/store/store";
import { updateSlideStatus } from "@/store/pipelineSlice";
import { SlideThumbnail } from "./SlideThumbnail";
import { SlidePreview } from "./SlidePreview";
import { NarrativePanel } from "./NarrativePanel";
import { useState } from "react";

export function GalleryView() {
  const { slides, narrativeSuggestions } = useSelector(
    (state: RootState) => state.pipeline
  );
  const dispatch = useDispatch();
  const [activeIndex, setActiveIndex] = useState(0);

  const confirmedCount = slides.filter((s) => s.status === "confirmed").length;
  const flaggedCount = slides.filter((s) => s.status === "flagged").length;

  const handleConfirm = (index: number) => {
    dispatch(updateSlideStatus({ index, status: "confirmed" }));
  };

  const handleFlag = (index: number, feedback: string) => {
    dispatch(updateSlideStatus({ index, status: "flagged", feedback }));
  };

  return (
    <div className="flex h-full">
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
              onConfirm={() => handleConfirm(activeIndex)}
              onFlag={(feedback) => handleFlag(activeIndex, feedback)}
            />
          )}
        </div>

        {narrativeSuggestions.length > 0 && (
          <NarrativePanel suggestions={narrativeSuggestions} />
        )}

        {/* Bottom: Progress + Actions */}
        <div className="border-t p-4 flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {confirmedCount}/{slides.length} confirmed, {flaggedCount} flagged
          </span>
          <div className="space-x-3">
            {flaggedCount > 0 && (
              <button className="px-4 py-2 bg-yellow-500 text-white rounded">
                Process flagged slides
              </button>
            )}
            <button className="px-4 py-2 bg-green-600 text-white rounded">
              Confirm all, generate PPT
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
