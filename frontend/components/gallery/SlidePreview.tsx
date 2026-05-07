"use client";

import { useState } from "react";

interface Slide {
  index: number;
  content: Record<string, unknown>;
  status: "pending" | "confirmed" | "flagged";
  feedback?: string;
}

interface Props {
  slide: Slide;
  onConfirm: () => void;
  onFlag: (feedback: string) => void;
}

export function SlidePreview({ slide, onConfirm, onFlag }: Props) {
  const [feedback, setFeedback] = useState("");
  const content = slide.content as {
    title?: string;
    body?: string;
    bullets?: string[];
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">{content.title || `Slide ${slide.index + 1}`}</h2>

      {content.body && <p className="text-gray-700">{content.body}</p>}

      {content.bullets && (
        <ul className="list-disc pl-6 space-y-1">
          {content.bullets.map((bullet, i) => (
            <li key={i}>{bullet}</li>
          ))}
        </ul>
      )}

      <div className="flex items-center space-x-3 pt-4 border-t">
        <button
          onClick={onConfirm}
          className="px-3 py-1 bg-green-600 text-white text-sm rounded"
        >
          Confirm
        </button>
        <input
          type="text"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Revision notes..."
          className="flex-1 border rounded px-2 py-1 text-sm"
        />
        <button
          onClick={() => {
            onFlag(feedback);
            setFeedback("");
          }}
          className="px-3 py-1 bg-yellow-500 text-white text-sm rounded"
        >
          Flag
        </button>
      </div>
    </div>
  );
}
