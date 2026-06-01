"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { requireOwner } from "@/lib/auth";
import { PILLAR_LABELS, PLATFORM_LABELS } from "@/lib/next-action";

const PILLAR_KEYS = Object.keys(PILLAR_LABELS);
const PLATFORM_KEYS = Object.keys(PLATFORM_LABELS);

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export async function createVideo(formData: FormData): Promise<void> {
  await requireOwner();
  const supabase = await createClient();

  const topic = (formData.get("topic") as string)?.trim();
  const pillar = (formData.get("pillar") as string) || null;
  const slug = ((formData.get("slug") as string) || slugify(topic)).trim();
  const platformTargets = formData
    .getAll("platform_targets")
    .map((v) => String(v))
    .filter((v) => PLATFORM_KEYS.includes(v));
  const notes = ((formData.get("notes") as string) || "").trim() || null;

  if (!topic || !slug) {
    throw new Error("Topic and slug are required.");
  }
  if (pillar && !PILLAR_KEYS.includes(pillar)) {
    throw new Error(`Unknown pillar: ${pillar}`);
  }

  const { error } = await supabase.from("videos").insert({
    slug,
    topic,
    pillar,
    platform_targets: platformTargets,
    state: "queued",
    notes,
  });
  if (error) {
    throw new Error(error.message);
  }

  redirect(`/videos/${slug}`);
}
