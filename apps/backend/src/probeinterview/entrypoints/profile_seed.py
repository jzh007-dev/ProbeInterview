"""Idempotent development data for the profile overview vertical slice."""

from uuid import UUID

from sqlalchemy import Engine, text

DEMO_USER_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1001")
DEMO_WECHAT_IDENTITY_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e1002")
DEMO_PROFILE_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e2001")
DEMO_SECONDARY_PROFILE_ID = UUID("018f7f64-3c6a-7d21-95a8-4d1b8c2e2002")


HISTORIC_SEED_APP_ID = "wx8f3c2a1d9e7b6c5a"


def seed_demo_profile(engine: Engine, *, wechat_app_id: str | None = None) -> None:
    """Upsert one deterministic user, identity, and two target profiles.

    The identity binds to the configured ``wechat_app_id`` so the fake
    adapter's ``<openid>`` login code resolves this user through the same
    ``(app_id, openid)`` lookup as a real exchange. ``local_test`` has no
    WeChat settings and keeps the historic binding value.
    """

    app_id = wechat_app_id if wechat_app_id else HISTORIC_SEED_APP_ID

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (id, nickname, avatar_object_key)
                values (:id, :nickname, null)
                on conflict (id) do update
                set nickname = excluded.nickname,
                    avatar_object_key = null,
                    updated_at = now()
                """
            ),
            {
                "id": DEMO_USER_ID,
                "nickname": "Bao",
            },
        )
        connection.execute(
            text(
                """
                insert into wechat_identities (id, user_id, app_id, openid, unionid)
                values (:id, :user_id, :app_id, :openid, :unionid)
                on conflict (id) do update
                set user_id = excluded.user_id,
                    app_id = excluded.app_id,
                    openid = excluded.openid,
                    unionid = excluded.unionid,
                    updated_at = now()
                """
            ),
            {
                "id": DEMO_WECHAT_IDENTITY_ID,
                "user_id": DEMO_USER_ID,
                "app_id": app_id,
                "openid": "oProbeInterviewDemoOpenId01",
                "unionid": "uProbeInterviewDemoUnionId1",
            },
        )
        connection.execute(
            text(
                """
                insert into candidate_profiles (
                    id,
                    user_id,
                    target_role,
                    relevant_experience_months,
                    is_default
                )
                values (
                    :id,
                    :user_id,
                    :target_role,
                    :relevant_experience_months,
                    :is_default
                )
                on conflict (id) do update
                set user_id = excluded.user_id,
                    target_role = excluded.target_role,
                    relevant_experience_months = excluded.relevant_experience_months,
                    is_default = excluded.is_default,
                    updated_at = now()
                """
            ),
            [
                {
                    "id": DEMO_PROFILE_ID,
                    "user_id": DEMO_USER_ID,
                    "target_role": "AI 全栈开发",
                    "relevant_experience_months": 84,
                    "is_default": True,
                },
                {
                    "id": DEMO_SECONDARY_PROFILE_ID,
                    "user_id": DEMO_USER_ID,
                    "target_role": "后端开发",
                    "relevant_experience_months": 60,
                    "is_default": False,
                },
            ],
        )
        connection.execute(
            text(
                """
                insert into knowledge_upload_policies (user_id)
                values (:user_id)
                on conflict (user_id) do nothing
                """
            ),
            {"user_id": DEMO_USER_ID},
        )
        connection.execute(
            text(
                """
                insert into user_capabilities (user_id, capability)
                values (:user_id, 'knowledge.submit_public')
                on conflict (user_id, capability) do nothing
                """
            ),
            {"user_id": DEMO_USER_ID},
        )
