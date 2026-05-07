interface Slide {
  index: number;
  content: Record<string, unknown>;
  status: "pending" | "confirmed" | "flagged";
}

interface Props {
  slide: Slide;
  isActive: boolean;
  onClick: () => void;
}

export function SlideThumbnail({ slide, isActive, onClick }: Props) {
  const statusIcon =
    slide.status === "confirmed"
      ? "✓"
      : slide.status === "flagged"
        ? "⚠"
        : "";

  return (
    <button
      onClick={onClick}
      className={`w-full p-2 rounded border text-left text-sm ${
        isActive ? "border-blue-500 bg-blue-50" : "border-gray-200"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium">Slide {slide.index + 1}</span>
        <span>{statusIcon}</span>
      </div>
    </button>
  );
}
