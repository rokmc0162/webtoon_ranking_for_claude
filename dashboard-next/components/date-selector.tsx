"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface DateSelectorProps {
  dates: string[];
  selected: string;
  onSelect: (date: string) => void;
}

function getDayOfWeek(dateStr: string): string {
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const d = new Date(dateStr + "T00:00:00");
  return days[d.getDay()];
}

export function DateSelector({ dates, selected, onSelect }: DateSelectorProps) {
  return (
    <Select value={selected} onValueChange={onSelect}>
      <SelectTrigger className="w-[200px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {dates.map((date) => (
          <SelectItem key={date} value={date}>
            {date} ({getDayOfWeek(date)})
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
