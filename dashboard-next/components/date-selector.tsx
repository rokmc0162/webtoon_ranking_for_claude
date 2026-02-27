"use client";

import { useState } from "react";
import { CalendarIcon } from "lucide-react";
import { ko } from "date-fns/locale/ko";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

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

function toLocalDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function toDateStr(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function DateSelector({ dates, selected, onSelect }: DateSelectorProps) {
  const [open, setOpen] = useState(false);

  const availableSet = new Set(dates);
  const selectedDate = toLocalDate(selected);

  const handleSelect = (day: Date | undefined) => {
    if (!day) return;
    const str = toDateStr(day);
    if (availableSet.has(str)) {
      onSelect(str);
      setOpen(false);
    }
  };

  // 데이터가 있는 날짜만 활성화
  const disabledMatcher = (day: Date) => {
    return !availableSet.has(toDateStr(day));
  };

  // 달력 표시 범위
  const oldestDate = dates.length > 0 ? toLocalDate(dates[dates.length - 1]) : undefined;
  const newestDate = dates.length > 0 ? toLocalDate(dates[0]) : undefined;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="w-[200px] justify-start text-left font-normal gap-2"
        >
          <CalendarIcon className="h-4 w-4 text-muted-foreground" />
          {selected} ({getDayOfWeek(selected)})
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={handleSelect}
          defaultMonth={selectedDate}
          disabled={disabledMatcher}
          fromDate={oldestDate}
          toDate={newestDate}
          locale={ko}
        />
      </PopoverContent>
    </Popover>
  );
}
