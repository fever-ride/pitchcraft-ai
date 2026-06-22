"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useTranslations } from "next-intl";

interface SlideStructure {
  slide_index: number;
  title: string;
  type: string;
  key_points: string[];
}

interface Props {
  pipelineId: string;
  onConfirm: (edits?: Record<string, unknown>) => void;
  disabled?: boolean;
}

export function HitlStructure({ pipelineId, onConfirm, disabled }: Props) {
  const t = useTranslations("pipeline");
  const [structure, setStructure] = useState<SlideStructure[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSlides(pipelineId).then((data) => {
      setStructure((data.deck_structure as SlideStructure[]) || []);
      setLoading(false);
    });
  }, [pipelineId]);

  const moveSlide = (index: number, direction: -1 | 1) => {
    const newStructure = [...structure];
    const target = index + direction;
    if (target < 0 || target >= newStructure.length) return;
    [newStructure[index], newStructure[target]] = [newStructure[target], newStructure[index]];
    newStructure.forEach((s, i) => (s.slide_index = i));
    setStructure(newStructure);
  };

  const removeSlide = (index: number) => {
    const newStructure = structure.filter((_, i) => i !== index);
    newStructure.forEach((s, i) => (s.slide_index = i));
    setStructure(newStructure);
  };

  const addSlide = () => {
    setStructure([
      ...structure,
      {
        slide_index: structure.length,
        title: "New Slide",
        type: "overview",
        key_points: [],
      },
    ]);
  };

  if (loading) {
    return <div className="p-8 text-center text-gray-500">{t("hitlStructure.loading")}</div>;
  }

  return (
    <div className="max-w-3xl mx-auto p-8 overflow-y-auto h-full">
      <h2 className="text-xl font-bold mb-4">{t("hitlStructure.title")}</h2>
      <p className="text-sm text-gray-600 mb-6">
        {t("hitlStructure.subtitle")}
      </p>

      <div className="space-y-2 mb-6">
        {structure.map((slide, i) => (
          <div key={i} className="flex items-center gap-3 border rounded p-3">
            <div className="flex flex-col gap-1">
              <button
                onClick={() => moveSlide(i, -1)}
                className="text-xs text-gray-400 hover:text-gray-700"
                disabled={i === 0}
              >
                ▲
              </button>
              <button
                onClick={() => moveSlide(i, 1)}
                className="text-xs text-gray-400 hover:text-gray-700"
                disabled={i === structure.length - 1}
              >
                ▼
              </button>
            </div>
            <div className="flex-1">
              <input
                type="text"
                value={slide.title}
                onChange={(e) => {
                  const updated = [...structure];
                  updated[i].title = e.target.value;
                  setStructure(updated);
                }}
                className="w-full text-sm font-medium border-b border-transparent hover:border-gray-300 focus:border-blue-500 outline-none px-1 py-0.5"
              />
              <span className="text-xs text-gray-400">{slide.type}</span>
            </div>
            <button
              onClick={() => removeSlide(i)}
              className="text-xs text-red-400 hover:text-red-600"
            >
              {t("hitlStructure.removeSlide")}
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 pt-4 border-t">
        <button
          onClick={addSlide}
          className="px-3 py-1 border rounded text-sm text-gray-600 hover:bg-gray-50"
        >
          {t("hitlStructure.addSlide")}
        </button>
        <div className="flex-1" />
        <button
          onClick={() => onConfirm({ deck_structure: structure })}
          disabled={disabled}
          className="px-4 py-2 bg-green-600 text-white rounded font-medium disabled:opacity-50"
        >
          {t("hitlStructure.confirmStructure", { count: structure.length })}
        </button>
      </div>
    </div>
  );
}
