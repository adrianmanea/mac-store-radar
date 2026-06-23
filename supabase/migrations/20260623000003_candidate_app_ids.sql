-- M9.5 app-set dedup: store each candidate's competitive set so near-duplicate niches
-- (same apps, different wording — e.g. "whatsapp mac" vs "whatsapp macos") can be collapsed.

alter table niche_candidates add column if not exists app_ids jsonb;
