"use client";

/**
 * Client-only FullCalendar wrapper (T-217) — avoids SSR crashes from FullCalendar DOM APIs.
 */

import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";

type CalendarEvent = {
  id: string;
  title: string;
  start: string;
  end: string;
  backgroundColor: string;
  borderColor: string;
  extendedProps?: { est_minutes: number };
};

export function StudyPlanCalendar({ events }: { events: CalendarEvent[] }) {
  return (
    <div className="overflow-x-auto" data-testid="fullcalendar-root">
      <FullCalendar
        plugins={[dayGridPlugin, timeGridPlugin]}
        initialView="dayGridMonth"
        headerToolbar={{
          left: "prev,next today",
          center: "title",
          right: "dayGridMonth,timeGridWeek",
        }}
        events={events}
        height="auto"
      />
    </div>
  );
}
