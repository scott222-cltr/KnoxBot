
import os
from supabase import create_client, Client

class Database:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")

        if not self.url:
            raise RuntimeError("SUPABASE_URL is missing.")

        if not self.key:
            raise RuntimeError("SUPABASE_KEY is missing.")

        self.client: Client = create_client(
            self.url,
            self.key
        )

    def table(self, table_name: str):
        """Return a Supabase table query."""
        return self.client.table(table_name)

    def get_guild_settings(self, guild_id: int):
        result = (
            self.client
            .table("guild_settings")
            .select("*")
            .eq("guild_id", str(guild_id))
            .limit(1)
            .execute()
        )

        if result.data:
            return result.data[0]

        return None

    def update_guild_config(self, guild_id: int, config: dict):
        existing = self.get_guild_settings(guild_id)

        if existing:
            current_config = existing.get("config") or {}
            current_config.update(config)

            return (
                self.client
                .table("guild_settings")
                .update({
                    "config": current_config
                })
                .eq("guild_id", str(guild_id))
                .execute()
            )

        return (
            self.client
            .table("guild_settings")
            .insert({
                "guild_id": str(guild_id),
                "config": config
            })
            .execute()
        )

    def log_event(
        self,
        guild_id: int,
        event_type: str,
        actor_id=None,
        target_id=None,
        details=None
    ):
        return (
            self.client
            .table("event_logs")
            .insert({
                "guild_id": str(guild_id),
                "event_type": event_type,
                "actor_id": str(actor_id) if actor_id else None,
                "target_id": str(target_id) if target_id else None,
                "details": details or {}
            })
            .execute()
        )


db = Database()
