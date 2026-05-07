interface NarrativeSuggestion {
  page: number;
  issue: string;
}

interface Props {
  suggestions: NarrativeSuggestion[];
}

export function NarrativePanel({ suggestions }: Props) {
  return (
    <div className="border-t bg-amber-50 p-4">
      <h3 className="text-sm font-semibold text-amber-800 mb-2">
        Narrative suggestions ({suggestions.length})
      </h3>
      <ul className="space-y-1">
        {suggestions.map((s, i) => (
          <li key={i} className="text-sm text-amber-700">
            <span className="font-medium">Slide {s.page + 1}:</span> {s.issue}
          </li>
        ))}
      </ul>
    </div>
  );
}
