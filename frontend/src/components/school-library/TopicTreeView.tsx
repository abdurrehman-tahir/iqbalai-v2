"use client";

import type { SchoolLibraryItemRead } from "@/lib/api/types";

export interface TopicTreeChapter {
  title: string;
  sections?: Array<{
    title: string;
    sub_topics?: string[];
  }>;
}

export interface TopicTreeData {
  chapters?: TopicTreeChapter[];
  parse_degraded?: boolean;
  parse_error?: string | null;
}

export function parseTopicTree(item: SchoolLibraryItemRead): TopicTreeData | null {
  if (!item.topic_tree_jsonb || typeof item.topic_tree_jsonb !== "object") {
    return null;
  }
  return item.topic_tree_jsonb as TopicTreeData;
}

interface TopicTreeViewProps {
  tree: TopicTreeData | null;
  degradedLabel: string;
  emptyLabel: string;
}

export function TopicTreeView({ tree, degradedLabel, emptyLabel }: TopicTreeViewProps) {
  if (!tree || !tree.chapters?.length) {
    return (
      <p className="text-sm text-gray-600" role="status">
        {tree?.parse_degraded ? degradedLabel : emptyLabel}
      </p>
    );
  }

  return (
    <ol className="space-y-4 list-decimal ps-5" aria-label="Curriculum topic tree">
      {tree.chapters.map((chapter) => (
        <li key={chapter.title} className="text-sm text-gray-900">
          <span className="font-semibold">{chapter.title}</span>
          {chapter.sections?.length ? (
            <ol className="mt-2 space-y-2 list-[lower-alpha] ps-5">
              {chapter.sections.map((section) => (
                <li key={`${chapter.title}-${section.title}`}>
                  <span className="font-medium">{section.title}</span>
                  {section.sub_topics?.length ? (
                    <ul className="mt-1 list-disc ps-5 text-gray-700">
                      {section.sub_topics.map((topic) => (
                        <li key={topic}>{topic}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
