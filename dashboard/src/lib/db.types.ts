export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      analyst_briefs: {
        Row: {
          created_at: string
          id: string
          metrics_snapshot: Json | null
          scout_brief_md: string
          summary_md: string
          week_start: string
        }
        Insert: {
          created_at?: string
          id?: string
          metrics_snapshot?: Json | null
          scout_brief_md: string
          summary_md: string
          week_start: string
        }
        Update: {
          created_at?: string
          id?: string
          metrics_snapshot?: Json | null
          scout_brief_md?: string
          summary_md?: string
          week_start?: string
        }
        Relationships: []
      }
      events: {
        Row: {
          created_at: string
          id: string
          level: string
          message: string | null
          payload: Json | null
          stage: string
          video_id: string | null
        }
        Insert: {
          created_at?: string
          id?: string
          level?: string
          message?: string | null
          payload?: Json | null
          stage: string
          video_id?: string | null
        }
        Update: {
          created_at?: string
          id?: string
          level?: string
          message?: string | null
          payload?: Json | null
          stage?: string
          video_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "events_video_id_fkey"
            columns: ["video_id"]
            isOneToOne: false
            referencedRelation: "videos"
            referencedColumns: ["id"]
          },
        ]
      }
      jobs: {
        Row: {
          attempts: number
          created_at: string
          ended_at: string | null
          error: string | null
          id: string
          payload: Json | null
          started_at: string | null
          status: string
          type: string
          video_id: string | null
        }
        Insert: {
          attempts?: number
          created_at?: string
          ended_at?: string | null
          error?: string | null
          id?: string
          payload?: Json | null
          started_at?: string | null
          status?: string
          type: string
          video_id?: string | null
        }
        Update: {
          attempts?: number
          created_at?: string
          ended_at?: string | null
          error?: string | null
          id?: string
          payload?: Json | null
          started_at?: string | null
          status?: string
          type?: string
          video_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "jobs_video_id_fkey"
            columns: ["video_id"]
            isOneToOne: false
            referencedRelation: "videos"
            referencedColumns: ["id"]
          },
        ]
      }
      metrics: {
        Row: {
          captured_at: string
          comments: number | null
          id: string
          likes: number | null
          platform: string
          retention_pct: number | null
          saves: number | null
          shares: number | null
          time_window: string
          video_id: string
          views: number | null
          watch_time_seconds: number | null
        }
        Insert: {
          captured_at?: string
          comments?: number | null
          id?: string
          likes?: number | null
          platform: string
          retention_pct?: number | null
          saves?: number | null
          shares?: number | null
          time_window: string
          video_id: string
          views?: number | null
          watch_time_seconds?: number | null
        }
        Update: {
          captured_at?: string
          comments?: number | null
          id?: string
          likes?: number | null
          platform?: string
          retention_pct?: number | null
          saves?: number | null
          shares?: number | null
          time_window?: string
          video_id?: string
          views?: number | null
          watch_time_seconds?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "metrics_video_id_fkey"
            columns: ["video_id"]
            isOneToOne: false
            referencedRelation: "videos"
            referencedColumns: ["id"]
          },
        ]
      }
      music_tracks: {
        Row: {
          bpm: number | null
          created_at: string
          duration_sec: number | null
          file_path: string
          id: string
          label: string
          license_credit: string | null
          license_source: string | null
          mood: string | null
        }
        Insert: {
          bpm?: number | null
          created_at?: string
          duration_sec?: number | null
          file_path: string
          id?: string
          label: string
          license_credit?: string | null
          license_source?: string | null
          mood?: string | null
        }
        Update: {
          bpm?: number | null
          created_at?: string
          duration_sec?: number | null
          file_path?: string
          id?: string
          label?: string
          license_credit?: string | null
          license_source?: string | null
          mood?: string | null
        }
        Relationships: []
      }
      ready_tray: {
        Row: {
          caption: string | null
          created_at: string
          deliverable_path: string | null
          description: string | null
          exported_at: string | null
          hashtags: string[]
          id: string
          music_credit: string | null
          on_screen_text: string[] | null
          platform: string
          posted_at: string | null
          pushed_at: string | null
          thumbnail_brief: string | null
          timestamps: string | null
          title: string | null
          updated_at: string
          video_id: string
        }
        Insert: {
          caption?: string | null
          created_at?: string
          deliverable_path?: string | null
          description?: string | null
          exported_at?: string | null
          hashtags?: string[]
          id?: string
          music_credit?: string | null
          on_screen_text?: string[] | null
          platform: string
          posted_at?: string | null
          pushed_at?: string | null
          thumbnail_brief?: string | null
          timestamps?: string | null
          title?: string | null
          updated_at?: string
          video_id: string
        }
        Update: {
          caption?: string | null
          created_at?: string
          deliverable_path?: string | null
          description?: string | null
          exported_at?: string | null
          hashtags?: string[]
          id?: string
          music_credit?: string | null
          on_screen_text?: string[] | null
          platform?: string
          posted_at?: string | null
          pushed_at?: string | null
          thumbnail_brief?: string | null
          timestamps?: string | null
          title?: string | null
          updated_at?: string
          video_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "ready_tray_video_id_fkey"
            columns: ["video_id"]
            isOneToOne: false
            referencedRelation: "videos"
            referencedColumns: ["id"]
          },
        ]
      }
      reminders: {
        Row: {
          created_at: string
          dismissed_at: string | null
          fire_at: string
          fired_at: string | null
          id: string
          platform: string
          time_window: string
          video_id: string
        }
        Insert: {
          created_at?: string
          dismissed_at?: string | null
          fire_at: string
          fired_at?: string | null
          id?: string
          platform: string
          time_window: string
          video_id: string
        }
        Update: {
          created_at?: string
          dismissed_at?: string | null
          fire_at?: string
          fired_at?: string | null
          id?: string
          platform?: string
          time_window?: string
          video_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "reminders_video_id_fkey"
            columns: ["video_id"]
            isOneToOne: false
            referencedRelation: "videos"
            referencedColumns: ["id"]
          },
        ]
      }
      video_assets: {
        Row: {
          candidate_idx: number
          created_at: string
          duration_sec: number | null
          file_path: string
          height: number | null
          id: string
          license: string | null
          needs_rights_check: boolean
          picked: boolean
          provider: string
          shot_id: string
          source_page: string | null
          video_id: string
          width: number | null
        }
        Insert: {
          candidate_idx: number
          created_at?: string
          duration_sec?: number | null
          file_path: string
          height?: number | null
          id?: string
          license?: string | null
          needs_rights_check?: boolean
          picked?: boolean
          provider: string
          shot_id: string
          source_page?: string | null
          video_id: string
          width?: number | null
        }
        Update: {
          candidate_idx?: number
          created_at?: string
          duration_sec?: number | null
          file_path?: string
          height?: number | null
          id?: string
          license?: string | null
          needs_rights_check?: boolean
          picked?: boolean
          provider?: string
          shot_id?: string
          source_page?: string | null
          video_id?: string
          width?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "video_assets_video_id_fkey"
            columns: ["video_id"]
            isOneToOne: false
            referencedRelation: "videos"
            referencedColumns: ["id"]
          },
        ]
      }
      videos: {
        Row: {
          created_at: string
          id: string
          notes: string | null
          pillar: string | null
          platform_targets: string[]
          rough_cut_path: string | null
          rough_cut_url: string | null
          script_md: string | null
          selections_json: Json | null
          shot_list_json: Json | null
          slug: string
          state: string
          thumbnail_storage_path: string | null
          topic: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          id?: string
          notes?: string | null
          pillar?: string | null
          platform_targets?: string[]
          rough_cut_path?: string | null
          rough_cut_url?: string | null
          script_md?: string | null
          selections_json?: Json | null
          shot_list_json?: Json | null
          slug: string
          state?: string
          thumbnail_storage_path?: string | null
          topic: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          id?: string
          notes?: string | null
          pillar?: string | null
          platform_targets?: string[]
          rough_cut_path?: string | null
          rough_cut_url?: string | null
          script_md?: string | null
          selections_json?: Json | null
          shot_list_json?: Json | null
          slug?: string
          state?: string
          thumbnail_storage_path?: string | null
          topic?: string
          updated_at?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      is_owner: { Args: never; Returns: boolean }
      query: { Args: { query: string }; Returns: undefined }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
