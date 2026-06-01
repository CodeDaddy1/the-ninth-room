/**
 * Map a video.state → the next slash command the user should run in Claude Code.
 *
 * Mirrors `worker/orchestrator/work_dir.py:NEXT_ACTION`. If we ever rebalance
 * the state machine, both files have to move in lockstep.
 */
export type NextActionKind = "agent" | "worker_job" | "manual";

export interface NextAction {
  kind: NextActionKind;
  /** The slash command to paste into Claude Code, work-dir embedded. */
  slash?: string;
  /** Worker job type, when the worker should do the work. */
  jobType?: "fetch" | "assemble" | "music_duck" | "ready_tray";
  /** Plain-English instruction (used when neither agent nor worker applies). */
  instruction?: string;
  /** Relative filename the watcher waits for. */
  expectFile: string;
  /** State the video transitions to once expectFile exists. */
  advancesTo: string;
}

export function getNextAction(state: string, slug: string, topic: string): NextAction | null {
  switch (state) {
    case "queued":
      return {
        kind: "agent",
        slash: `/youtube-scriptwriter slug=${slug} topic="${topic}"`,
        expectFile: "script.md",
        advancesTo: "scripting",
      };
    case "scripting":
      return {
        kind: "agent",
        slash: `/asset-scout slug=${slug}`,
        expectFile: "shot_list.json",
        advancesTo: "shots",
      };
    case "shots":
      return {
        kind: "worker_job",
        jobType: "fetch",
        expectFile: "assets/",
        advancesTo: "fetching",
      };
    case "fetching":
      return {
        kind: "manual",
        instruction: "Worker is fetching stock candidates. No action required.",
        expectFile: "assets/",
        advancesTo: "awaiting_vo",
      };
    case "awaiting_vo":
      return {
        kind: "manual",
        instruction:
          "Record the voiceover and save it as voiceover.mp3 in the work dir.",
        expectFile: "voiceover.mp3",
        advancesTo: "assembling",
      };
    case "assembling":
      return {
        kind: "worker_job",
        jobType: "assemble",
        expectFile: "rough_cut.mp4",
        advancesTo: "ready",
      };
    case "ready":
      return {
        kind: "agent",
        slash: `/visual-director slug=${slug}`,
        expectFile: "visuals.json",
        advancesTo: "tray",
      };
    case "tray":
      return {
        kind: "manual",
        instruction:
          "Ready tray populated. Review the per-platform copy, then push to device.",
        expectFile: "tray/",
        advancesTo: "pushed",
      };
    case "pushed":
      return {
        kind: "manual",
        instruction: "Post from your phone, then click 'I posted it'.",
        expectFile: "",
        advancesTo: "published",
      };
    default:
      return null;
  }
}

export const PILLAR_LABELS: Record<string, string> = {
  hidden_in_plain_sight: "Hidden in Plain Sight",
  unsolved: "Unsolved & Unexplained",
  how_it_works: "How It Really Works",
  lost_forgotten: "Lost & Forgotten",
  scales_of_wonder: "Scales of Wonder",
  human_strange: "The Human Strange",
};

export const PLATFORM_LABELS: Record<string, string> = {
  youtube_long: "YouTube long-form",
  youtube_short: "YouTube Short",
  instagram_reel: "Instagram Reel",
  instagram_carousel: "Instagram Carousel",
  instagram_story: "Instagram Story",
};

export const STATE_LABELS: Record<string, string> = {
  queued: "Queued",
  scripting: "Scripting",
  shots: "Shot list",
  fetching: "Fetching assets",
  awaiting_vo: "Awaiting VO",
  assembling: "Assembling",
  ready: "Rough cut ready",
  tray: "Tray ready",
  pushed: "Pushed to device",
  published: "Published",
};
