PLAYER_PROFILE_FIELDS = {
    "date_of_birth": {"type": "string", "format": "date", "nullable": True, "description": "YYYY-MM-DD, not in the future."},
    "height_cm": {"type": "integer", "minimum": 100, "maximum": 230, "nullable": True},
    "bio": {"type": "string", "maxLength": 400},
    "image_data": {"type": "string", "description": "Optional data:image/png, data:image/jpeg, or data:image/webp URL, base64 encoded, maximum 170 KB decoded."},
    "goals": {"type": "integer", "minimum": 0, "maximum": 999},
    "assists": {"type": "integer", "minimum": 0, "maximum": 999},
    "apps": {"type": "integer", "minimum": 0, "maximum": 999, "description": "Appearances."},
    "starts": {"type": "integer", "minimum": 0, "description": "Cannot exceed apps."},
    "minutes": {"type": "integer", "minimum": 0, "description": "At most 120 per appearance."},
    "yellow_cards": {"type": "integer", "minimum": 0, "maximum": 99},
    "red_cards": {"type": "integer", "minimum": 0, "maximum": 99},
    "clean_sheets": {"type": "integer", "minimum": 0, "description": "Cannot exceed apps."},
    "saves": {"type": "integer", "minimum": 0, "maximum": 9999},
}

def openapi_spec():
    bearer = {"type": "http", "scheme": "bearer", "bearerFormat": "Opaque session token"}

    def ok(schema_ref):
        return {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "ok": {"type": "boolean", "example": True},
                                "data": {"$ref": schema_ref},
                            },
                        }
                    }
                },
            }
        }

    def ref(name):
        return f"#/components/schemas/{name}"

    error_response = {
        "description": "API error",
        "content": {
            "application/json": {
                "schema": {"$ref": ref("Error")},
                "example": {
                    "ok": False,
                    "error": {"code": "invalid_field", "message": "Enter a valid email address."},
                },
            }
        },
    }

    paths = {
        "/api/v1/health": {
            "get": {
                "tags": ["Public"],
                "summary": "Service health",
                "security": [],
                "responses": ok(ref("Health")),
            }
        },
        "/api/v1/auth/admin": {
            "post": {
                "tags": ["Auth"],
                "summary": "Sign in as an administrator",
                "description": "Used by the private super-admin sign-in page. Admin credentials are provisioned from server environment variables.",
                "security": [],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["email", "password"], "properties": {"email": {"type": "string", "format": "email"}, "password": {"type": "string"}}}}},
                },
                "responses": {**ok(ref("Session")), "401": error_response, "403": error_response},
            }
        },
        "/api/v1/auth/register": {
            "post": {
                "tags": ["Auth"],
                "summary": "Create an unverified member account and send verification email",
                "security": [],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "email", "password"],
                                "properties": {
                                    "name": {"type": "string", "maxLength": 50},
                                    "email": {"type": "string", "format": "email"},
                                    "password": {"type": "string", "minLength": 8},
                                    "player_invite": {"type": "string", "description": "Optional single-use invitation token; registration links the new account to the invited community and player profile."},
                                },
                            }
                        }
                    },
                },
                "responses": {**ok(ref("Registration")), "400": error_response, "409": error_response, "503": error_response},
            }
        },
        "/api/v1/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "Log in; returns a session or a 2FA challenge",
                "security": [],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "password"],
                                "properties": {
                                    "email": {"type": "string", "format": "email"},
                                    "password": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {**ok(ref("Session")), "401": error_response},
            }
        },
        "/api/v1/auth/logout": {
            "post": {
                "tags": ["Auth"],
                "summary": "Revoke the current session",
                "security": [{"BearerAuth": []}],
                "responses": ok({"type": "object", "properties": {"revoked": {"type": "boolean"}}}),
            }
        },
        "/api/v1/me": {
            "get": {"tags": ["Auth"], "summary": "Current user", "security": [{"BearerAuth": []}], "responses": ok(ref("User"))}
        },
        "/api/v1/bootstrap": {
            "get": {
                "tags": ["Web app"],
                "summary": "Everything needed to render the clubhouse",
                "responses": ok(ref("Bootstrap")),
            }
        },
        "/api/v1/posts": {
            "get": {
                "tags": ["Feed"],
                "summary": "List posts",
                "parameters": [
                    {"name": "community_id", "in": "query", "schema": {"type": "string"}},
                    {"name": "tag", "in": "query", "schema": {"type": "string", "enum": ["club", "matchday", "tactics"]}},
                ],
                "responses": ok({"type": "array", "items": {"$ref": ref("Post")}}),
            },
            "post": {
                "tags": ["Feed"],
                "summary": "Create a post",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["community_id", "text"],
                                "properties": {
                                    "community_id": {"type": "string"},
                                    "text": {"type": "string", "maxLength": 500},
                                    "tag": {"type": "string", "enum": ["club", "matchday", "tactics"]},
                                },
                            }
                        }
                    },
                },
                "responses": ok(ref("Post")),
            },
        },
        "/api/v1/posts/{post_id}": {
            "delete": {
                "tags": ["Feed"],
                "summary": "Delete a post as its author, a community admin, or the super admin",
                "parameters": [{"name": "post_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Post and its dependent comments and likes deleted"}, "403": error_response, "404": error_response},
            },
        },
        "/api/v1/posts/{post_id}/like": {
            "post": {
                "tags": ["Feed"],
                "summary": "Toggle a like on a post",
                "parameters": [{"name": "post_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok(ref("Post")),
            }
        },
        "/api/v1/posts/{post_id}/comments": {
            "post": {
                "tags": ["Feed"],
                "summary": "Add a comment",
                "parameters": [{"name": "post_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["text"],
                                "properties": {"text": {"type": "string", "maxLength": 220}},
                            }
                        }
                    },
                },
                "responses": ok(ref("Post")),
            }
        },
        "/api/v1/polls": {
            "get": {"tags": ["Polls"], "summary": "List polls", "responses": ok({"type": "array", "items": {"$ref": ref("Poll")}})},
            "post": {
                "tags": ["Polls"],
                "summary": "Create a poll",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["question"],
                                "properties": {
                                    "question": {"type": "string", "maxLength": 120},
                                    "category": {"type": "string", "enum": ["Pickup", "Competition", "Lineup", "Tactics", "Club"], "default": "Pickup"},
                                    "duration_hours": {"type": "integer", "minimum": 1, "maximum": 168},
                                    "closes_at": {"type": "string", "format": "date-time", "description": "Exact poll closing timestamp; takes precedence over duration_hours."},
                                    "game_at": {"type": "string", "format": "date-time", "description": "Required for Pickup and Competition polls. Feedback email is scheduled for 10:00 local time for games from 05:00–08:00, otherwise 22:00 local time."},
                                    "location": {"type": "string", "maxLength": 160, "description": "Pickup venue or meeting point."},
                                    "options": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "string"}},
                                    "community_id": {"type": "string", "description": "Optional community scope. The caller must be a member of this community."},
                                },
                            }
                        }
                    },
                },
                "responses": ok(ref("Poll")),
            },
        },
        "/api/v1/polls/{poll_id}/vote": {
            "post": {
                "tags": ["Polls"],
                "summary": "Vote or change a vote",
                "parameters": [{"name": "poll_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["option_id"],
                                "properties": {"option_id": {"type": "string"}, "player_id": {"type": "string", "description": "Required when voting Yes on a Pickup poll; must identify the single active community player whose name matches the authenticated account name."}, "guest_count": {"type": "integer", "minimum": 0, "maximum": 2, "description": "Optional unregistered friends or family joining that player; Pickup Yes votes only."}},
                            }
                        }
                    },
                },
                "responses": ok(ref("Poll")),
            }
        },
        "/api/v1/polls/{poll_id}/teams": {
            "post": {
                "tags": ["Polls"], "summary": "Manually rearrange the balanced pickup teams after the poll closes",
                "parameters": [{"name": "poll_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["team_a", "team_b"], "properties": {"team_a": {"type": "array", "items": {"type": "string"}}, "team_b": {"type": "array", "items": {"type": "string"}}, "floater": {"type": "string", "nullable": True}}}}}},
                "responses": {**ok(ref("Poll")), "403": error_response, "409": error_response},
            }
        },
        "/api/v1/polls/{poll_id}/feedback": {
            "get": {"tags": ["Polls"], "summary": "Get post-game player rating form (admins also receive results)", "parameters": [{"name": "poll_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Feedback form and optional admin results"}, "403": error_response, "409": error_response}},
            "post": {"tags": ["Polls"], "summary": "Submit a rating and optional feedback for every roster player", "parameters": [{"name": "poll_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["ratings"], "properties": {"ratings": {"type": "array", "items": {"type": "object", "required": ["player_id", "value"], "properties": {"player_id": {"type": "string"}, "value": {"type": "integer", "minimum": 1, "maximum": 10}, "feedback": {"type": "string", "maxLength": 500}}}}}}}}}, "responses": {"200": {"description": "Ratings saved"}, "400": error_response, "403": error_response, "409": error_response}},
        },
        "/api/v1/communities": {
            "get": {"tags": ["Communities"], "summary": "List communities", "responses": ok({"type": "array", "items": {"$ref": ref("Community")}})},
            "post": {
                "tags": ["Communities"],
                "summary": "Create a community",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "sport", "description"],
                                "properties": {
                                    "name": {"type": "string", "maxLength": 48},
                                    "sport": {"type": "string"},
                                    "description": {"type": "string", "maxLength": 220},
                                    "privacy": {"type": "string", "enum": ["Public", "Private"]},
                                    "create_poll": {"type": "boolean"},
                                    "logo_data": {"type": "string", "description": "Optional base64 data URL for a PNG, JPEG, or WebP image."},
                                    "banner_data": {"type": "string", "description": "Optional base64 data URL for a PNG, JPEG, or WebP image."},
                                },
                            }
                        }
                    },
                },
                "responses": ok(ref("Community")),
            },
        },
        "/api/v1/communities/{community_id}": {"patch": {"tags": ["Communities"], "summary": "Update a community logo or banner (community admins only)", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {"logo_data": {"type": "string", "nullable": True}, "banner_data": {"type": "string", "nullable": True}}}}}}, "responses": {"200": {"description": "Updated community branding"}, "400": error_response, "403": error_response}}},
        "/api/v1/communities/{community_id}/fixtures/{fixture_id}/ratings/request": {"post": {"tags": ["Communities"], "summary": "Email community members an after-match player rating link (admins only)", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Rating request sent"}, "403": error_response, "409": error_response, "503": error_response}}},
        "/api/v1/communities/{community_id}/fixtures/{fixture_id}/ratings": {"get": {"tags": ["Communities"], "summary": "Get after-match rating form for a community member", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Fixture and player rating form"}, "403": error_response, "404": error_response}}, "post": {"tags": ["Communities"], "summary": "Submit 1 to 10 ratings and optional feedback for every player", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "fixture_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["ratings"], "properties": {"ratings": {"type": "array", "items": {"type": "object", "required": ["player_id", "value"], "properties": {"player_id": {"type": "string"}, "value": {"type": "integer", "minimum": 1, "maximum": 10}, "feedback": {"type": "string", "maxLength": 500}}}}}}}}}, "responses": {"200": {"description": "Ratings submitted"}, "403": error_response, "400": error_response}}},
        "/api/v1/communities/{community_id}/join": {
            "post": {
                "tags": ["Communities"],
                "summary": "Request to join a public community (platform admins may enter directly)",
                "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {**ok(ref("Community")), "403": error_response},
            }
        },
        "/api/v1/communities/{community_id}/join-requests": {
            "get": {"tags": ["Communities"], "summary": "List pending join requests (community admin or super admin)", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok({"type": "array", "items": {"type": "object"}}), "403": error_response}},
            "post": {"tags": ["Communities"], "summary": "Request to join a public community", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok(ref("Community")), "403": error_response}},
        },
        "/api/v1/communities/{community_id}/join-requests/{user_id}/decision": {"post": {"tags": ["Communities"], "summary": "Approve or decline a pending join request", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["decision"], "properties": {"decision": {"type": "string", "enum": ["approve", "deny"]}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "404": error_response}}},
        "/api/v1/communities/{community_id}/members": {
            "get": {"tags": ["Communities"], "summary": "List members and community roles", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": ok({"type": "array", "items": {"type": "object"}})},
            "post": {"tags": ["Communities"], "summary": "Add a verified registered user by email", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["email"], "properties": {"email": {"type": "string", "format": "email"}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "404": error_response, "409": error_response}}
        },
        "/api/v1/communities/{community_id}/poll-retention-settings": {
            "get": {"tags": ["Communities"], "summary": "Read poll cleanup age for a community (community admin or super admin)", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok({"type": "object"}), "403": error_response}},
            "patch": {"tags": ["Communities"], "summary": "Set poll cleanup age for a community (community admin or super admin)", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["days"], "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 30}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "400": error_response}}
        },
        "/api/v1/communities/{community_id}/invites": {"post": {"tags": ["Communities"], "summary": "Create a seven day community invite link", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok({"type": "object"}), "403": error_response}}},
        "/api/v1/community-invites/accept": {"post": {"tags": ["Communities"], "summary": "Accept a community invitation", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["token"], "properties": {"token": {"type": "string"}}}}}}, "responses": {**ok(ref("Community")), "404": error_response}}},
        "/api/v1/communities/{community_id}/deletion-requests": {"post": {"tags": ["Communities"], "summary": "Request community deletion; every current admin must approve", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok({"type": "object"}), "403": error_response, "409": error_response}}},
        "/api/v1/communities/{community_id}/deletion-request": {"get": {"tags": ["Communities"], "summary": "Get this community’s latest deletion request", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": ok({"type": "object"})}},
        "/api/v1/communities/{community_id}/deletion-requests/{request_id}/approve": {"post": {"tags": ["Communities"], "summary": "Approve a community deletion request", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "request_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok({"type": "object"}), "403": error_response, "409": error_response}}},
        "/api/v1/admin/community-deletions": {"get": {"tags": ["Admin"], "summary": "List deletion requests, timeout, and poll retention setting (super admin only)", "responses": {**ok({"type": "object"}), "403": error_response}}},
        "/api/v1/admin/community-deletion-settings": {"patch": {"tags": ["Admin"], "summary": "Set the number of days before unreviewed approved requests auto-delete (super admin only)", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["days"], "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 30}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response}}},
        "/api/v1/admin/poll-retention-settings": {"patch": {"tags": ["Admin"], "summary": "Set the default poll retention period in days (super admin only)", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["days"], "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 30}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "400": error_response}}},
        "/api/v1/admin/app-theme": {"patch": {"tags": ["Admin"], "summary": "Set the global app theme (super admin only)", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["theme"], "properties": {"theme": {"type": "string", "enum": ["light", "dark"]}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "400": error_response}}},
        "/api/v1/communities/{community_id}/theme": {"patch": {"tags": ["Communities"], "summary": "Set a community profile theme (community admin or super admin)", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["theme"], "properties": {"theme": {"type": "string", "enum": ["light", "dark"]}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "400": error_response}}},
        "/api/v1/admin/community-deletions/{request_id}/decision": {"post": {"tags": ["Admin"], "summary": "Approve or deny deletion (super admin only)", "parameters": [{"name": "request_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["decision"], "properties": {"decision": {"type": "string", "enum": ["approve", "deny"]}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "409": error_response}}},
        "/api/v1/communities/{community_id}/members/{user_id}": {
            "patch": {"tags": ["Communities"], "summary": "Promote or demote a community member", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["role"], "properties": {"role": {"type": "string", "enum": ["Admin", "Member"]}}}}}}, "responses": {**ok({"type": "object"}), "403": error_response, "409": error_response}},
            "delete": {"tags": ["Communities"], "summary": "Remove a community member; admins must first be demoted and a community must retain an admin", "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {**ok({"type": "object"}), "403": error_response, "404": error_response, "409": error_response}}
        },
        "/api/v1/team": {
            "get": {"tags": ["Team"], "summary": "Get the team, roster and lineup", "responses": ok(ref("Team"))}
        },
        "/api/v1/teams": {
            "post": {
                "tags": ["Team"],
                "summary": "Create a team for a community admin manages",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["community_id", "name", "age_group", "league", "coach"], "properties": {"community_id": {"type": "string"}, "name": {"type": "string"}, "age_group": {"type": "string"}, "league": {"type": "string"}, "coach": {"type": "string"}, "formation": {"type": "string", "enum": ["4-3-3", "4-2-3-1", "3-5-2"]}}}}},
                },
                "responses": {**ok(ref("Team")), "403": error_response, "409": error_response},
            }
        },
        "/api/v1/teams/{team_id}": {
            "patch": {
                "tags": ["Team"],
                "summary": "Update formation, starting XI or publish the team sheet (admin/coach)",
                "parameters": [{"name": "team_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "formation": {"type": "string", "enum": ["4-3-3", "4-2-3-1", "3-5-2"]},
                                    "starting_xi": {"type": "array", "minItems": 11, "maxItems": 11, "items": {"oneOf": [{"type": "string"}, {"type": "null"}], "description": "Player id or null for a manually assigned empty slot."}},
                                    "publish": {"type": "boolean"},
                                },
                            }
                        }
                    },
                },
                "responses": ok(ref("Team")),
            }
        },
        "/api/v1/players": {
            "get": {"tags": ["Team"], "summary": "List players", "responses": ok({"type": "array", "items": {"$ref": ref("Player")}})},
            "post": {
                "tags": ["Team"],
                "summary": "Add a registered account as a player or email an account registration invitation (community admin/super admin)",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "name", "number", "pos"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "description": "Existing verified accounts are linked immediately; otherwise a registration link is emailed."},
                                    "name": {"type": "string", "maxLength": 50},
                                    "number": {"type": "integer", "minimum": 1, "maximum": 99},
                                    "pos": {"type": "string"},
                                    "foot": {"type": "string", "enum": ["Right", "Left", "Both"]},
                                    "status": {"type": "string", "enum": ["available", "doubtful", "out"]},
                                    "xi_slot": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Optional Starting XI slot to fill when the player joins."},
                                    **PLAYER_PROFILE_FIELDS,
                                },
                            }
                        }
                    },
                },
                "responses": ok({"oneOf": [ref("Player"), {"type": "object", "properties": {"invitationPending": {"type": "boolean"}, "email": {"type": "string", "format": "email"}, "name": {"type": "string"}, "expiresAt": {"type": "string", "format": "date-time"}}}]}),
            },
        },
        "/api/v1/players/{player_id}": {
            "get": {
                "tags": ["Team"],
                "summary": "Get a player",
                "parameters": [{"name": "player_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok(ref("Player")),
            },
            "patch": {
                "tags": ["Team"],
                "summary": "Update a player (admin/coach)",
                "parameters": [{"name": "player_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": ref("PlayerUpdate")}}},
                },
                "responses": ok(ref("Player")),
            },
            "delete": {
                "tags": ["Team"],
                "summary": "Remove a player (admin/coach)",
                "description": "Removes the player and leaves their Starting XI position empty for manual replacement. Returns 409 squad_too_small if the roster would drop below 11.",
                "parameters": [{"name": "player_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok({
                    "type": "object",
                    "properties": {
                        "deleted": {"type": "boolean"},
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                }),
            },
        },
        "/api/v1/players/{player_id}/ratings": {
            "post": {
                "tags": ["Team"],
                "summary": "Rate a player from 1 to 10",
                "parameters": [{"name": "player_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["value"],
                                "properties": {"value": {"type": "number", "minimum": 1, "maximum": 10}},
                            }
                        }
                    },
                },
                "responses": ok(ref("Player")),
            }
        },
        "/api/v1/plans": {
            "get": {"tags": ["Game plans"], "summary": "List plans", "responses": ok({"type": "array", "items": {"$ref": ref("Plan")}})},
            "post": {
                "tags": ["Game plans"],
                "summary": "Create a community game plan",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["title", "opponent", "date", "venue", "objective"],
                                "properties": {
                                    "title": {"type": "string"},
                                    "opponent": {"type": "string"},
                                    "date": {"type": "string", "format": "date-time"},
                                    "venue": {"type": "string"},
                                    "formation": {"type": "string", "enum": ["4-3-3", "4-2-3-1", "3-5-2"]},
                                    "objective": {"type": "string"},
                                    "team_id": {"type": "string", "description": "The community team to attach this plan to."},
                                    "board": {"type": "array", "minItems": 11, "maxItems": 11, "items": {"type": "string"}, "description": "Optional ordered starting XI player IDs from the community roster."},
                                },
                            }
                        }
                    },
                },
                "responses": ok(ref("Plan")),
            },
        },
        "/api/v1/plans/{plan_id}": {
            "get": {
                "tags": ["Game plans"],
                "summary": "Get a plan visible to the caller's community",
                "parameters": [{"name": "plan_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok(ref("Plan")),
            },
            "patch": {
                "tags": ["Game plans"], "summary": "Edit match, tactical and player board fields (community admin)",
                "parameters": [{"name": "plan_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "description": "Send any editable match fields, tactical text/arrays, or an 11-player board."}}}},
                "responses": {**ok(ref("Plan")), "400": error_response, "403": error_response},
            },
        },
        "/api/v1/plans/{plan_id}/checklist/{check_id}": {
            "patch": {
                "tags": ["Game plans"],
                "summary": "Toggle or set a checklist item",
                "parameters": [
                    {"name": "plan_id", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "check_id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": {"done": {"type": "boolean"}}}
                        }
                    },
                },
                "responses": ok(ref("Plan")),
            }
        },
        "/api/v1/notifications": {
            "get": {"tags": ["Notifications"], "summary": "List notifications", "responses": ok({"type": "array", "items": {"$ref": ref("Notification")}})}
        },
        "/api/v1/notifications/read": {
            "post": {
                "tags": ["Notifications"],
                "summary": "Mark notifications as read",
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "all": {"type": "boolean"},
                                    "ids": {"type": "array", "items": {"type": "string"}},
                                },
                            }
                        }
                    },
                },
                "responses": ok({"type": "array", "items": {"$ref": ref("Notification")}}),
            }
        },
        "/api/v1/pickup/teams": {
            "get": {
                "tags": ["Pickup"],
                "summary": "Calculate balanced pickup teams",
                "parameters": [
                    {"name": "include_doubtful", "in": "query", "schema": {"type": "boolean", "default": False}},
                    {"name": "position_aware", "in": "query", "schema": {"type": "boolean", "default": True}},
                    {"name": "seed", "in": "query", "schema": {"type": "integer", "default": 0}},
                ],
                "responses": ok(ref("PickupResult")),
            }
        },
        "/api/v1/calendar": {
            "get": {
                "tags": ["Club"],
                "summary": "Calendar entries for a date range",
                "description": "Matches, club events and duties merged and sorted by time. Dates are UTC. Default: the current month. Maximum span 93 days.",
                "parameters": [
                    {"name": "community_id", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "from", "in": "query", "required": False, "schema": {"type": "string", "format": "date"}},
                    {"name": "to", "in": "query", "required": False, "schema": {"type": "string", "format": "date"}},
                ],
                "responses": ok({
                    "type": "object",
                    "properties": {
                        "from": {"type": "string", "format": "date"},
                        "to": {"type": "string", "format": "date"},
                        "entries": {"type": "array", "items": {"$ref": ref("CalendarEntry")}},
                    },
                }),
            }
        },
        "/api/v1/calendar/events": {
            "post": {
                "tags": ["Club"],
                "summary": "Add a private calendar event for a community",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["community_id", "title", "date"], "properties": {"community_id": {"type": "string"}, "title": {"type": "string"}, "date": {"type": "string", "format": "date-time"}, "type": {"type": "string"}, "detail": {"type": "string"}}}}}},
                "responses": {**ok({"type": "object"}), "403": error_response},
            }
        },
        "/api/v1/duties": {
            "post": {
                "tags": ["Club"],
                "summary": "Add a matchday duty for a signed-in community member",
                "description": "The member must belong to community_id. Rate limited to 30 per user per hour. Returns 409 duty_limit when the calendar is full.",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": ref("DutyInput")}}}},
                "responses": ok({"oneOf": [ref("Duty"), {"type": "object", "properties": {"duties": {"type": "array", "items": ref("Duty")}}}]}),
            }
        },
        "/api/v1/duties/{duty_id}/claim": {
            "post": {
                "tags": ["Club"],
                "summary": "Take a duty (first come, first served)",
                "description": "Returns 409 already_claimed if someone else has it, and 409 claim_limit when the member already has two duties that day.",
                "parameters": [{"name": "duty_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok(ref("Duty")),
            },
            "delete": {
                "tags": ["Club"],
                "summary": "Give a duty back",
                "description": "Allowed for the person who took it, a community admin, or the platform super admin.",
                "parameters": [{"name": "duty_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok(ref("Duty")),
            },
        },
        "/api/v1/duties/{duty_id}": {
            "delete": {
                "tags": ["Club"],
                "summary": "Delete a duty",
                "description": "Allowed for the person who added it, a community admin, or the platform super admin.",
                "parameters": [{"name": "duty_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": ok({"type": "object", "properties": {"deleted": {"type": "boolean"}, "id": {"type": "string"}, "title": {"type": "string"}}}),
            }
        },
        "/api/v1/schedule": {
            "get": {"tags": ["Club"], "summary": "Schedule and fixtures for one community", "parameters": [{"name": "community_id", "in": "query", "required": True, "schema": {"type": "string"}}], "responses": ok({"type": "object"})}
        },
    }

    json_body = lambda required: {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": required, "additionalProperties": True}}}}
    for path, summary, required in [
        ("/api/v1/auth/verify-email", "Verify an email address", ["token"]),
        ("/api/v1/auth/verification/resend", "Resend email verification", ["email"]),
        ("/api/v1/auth/password/forgot", "Request a password reset", ["email"]),
        ("/api/v1/auth/password/reset", "Set a new password", ["token", "password"]),
        ("/api/v1/auth/password/change", "Change the signed-in user's password", ["current_password", "new_password"]),
        ("/api/v1/auth/2fa/login", "Complete two-factor sign in", ["challengeToken", "code"]),
        ("/api/v1/auth/2fa/enable", "Enable two-factor authentication", ["code"]),
        ("/api/v1/auth/2fa/disable", "Disable two-factor authentication", ["password", "code"]),
    ]:
        protected = path.endswith(("/password/change", "/2fa/enable", "/2fa/disable"))
        paths[path] = {"post": {"tags": ["Auth"], "summary": summary, "security": [{"BearerAuth": []}] if protected else [], "requestBody": json_body(required), "responses": {"200": {"description": summary + " result"}, "400": error_response, "401": error_response, "429": error_response}}}
    paths["/api/v1/auth/2fa/setup"] = {"post": {"tags": ["Auth"], "summary": "Begin two-factor setup", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Authenticator secret and provisioning URI"}, "503": error_response}}}
    paths["/api/v1/me/api-key"] = {
        "get": {"tags": ["Auth"], "summary": "View API key request and active key status", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Key status without disclosing the secret"}}},
        "delete": {"tags": ["Auth"], "summary": "Revoke the current user's active API key", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Key revoked"}}},
    }
    paths["/api/v1/me/api-key-requests"] = {"post": {"tags": ["Auth"], "summary": "Request super-admin approval for an API key", "security": [{"BearerAuth": []}], "requestBody": json_body(["reason"]), "responses": {"200": {"description": "Request status"}, "409": error_response}}}
    paths["/api/v1/me/api-key-claim"] = {"post": {"tags": ["Auth"], "summary": "Claim an approved API key; the secret is returned once", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "One-time API key secret"}, "409": error_response}}}
    paths["/api/v1/admin/api-key-requests"] = {"get": {"tags": ["Auth"], "summary": "List pending API key requests (super admin only)", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Pending requests"}, "403": error_response}}}
    paths["/api/v1/theme"] = {"get": {"tags": ["Admin"], "summary": "Read the global app theme", "security": [], "responses": {"200": {"description": "App theme"}}}}
    paths["/api/v1/auth/google/config"] = {"get": {"tags": ["Auth"], "summary": "Check whether Google sign-in is configured", "security": [], "responses": {"200": {"description": "Google sign-in availability"}}}}
    paths["/api/v1/auth/google/start"] = {"post": {"tags": ["Auth"], "summary": "Start Google sign-in or account creation", "security": [], "requestBody": json_body([]), "responses": {"200": {"description": "Google authorization URL"}, "429": error_response, "503": error_response}}}
    paths["/api/v1/auth/google/callback"] = {"post": {"tags": ["Auth"], "summary": "Validate a Google authorization response and sign in or create an account", "security": [], "requestBody": json_body(["code", "state"]), "responses": {"200": {"description": "Authenticated session"}, "400": error_response, "401": error_response, "403": error_response}}}
    paths["/api/v1/admin/api-key-requests/{request_id}/decision"] = {"post": {"tags": ["Auth"], "summary": "Approve or deny an API key request (super admin only)", "security": [{"BearerAuth": []}], "parameters": [{"name": "request_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": json_body(["decision"]), "responses": {"200": {"description": "Request decision"}, "403": error_response}}}
    paths["/api/v1/communities/{community_id}/messages"] = {
        "get": {"tags": ["Communities"], "summary": "List member chat messages", "security": [{"BearerAuth": []}], "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Up to 100 messages"}, "403": error_response}},
        "post": {"tags": ["Communities"], "summary": "Post a community chat message", "security": [{"BearerAuth": []}], "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": json_body(["text"]), "responses": {"200": {"description": "Created message"}, "403": error_response}},
    }
    paths["/api/v1/communities/{community_id}/messages/{message_id}"] = {
        "patch": {"tags": ["Communities"], "summary": "Edit your own community chat message", "security": [{"BearerAuth": []}], "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "message_id", "in": "path", "required": True, "schema": {"type": "string"}}], "requestBody": json_body(["text"]), "responses": {"200": {"description": "Updated message"}, "403": error_response, "404": error_response}},
        "delete": {"tags": ["Communities"], "summary": "Delete your own community chat message", "security": [{"BearerAuth": []}], "parameters": [{"name": "community_id", "in": "path", "required": True, "schema": {"type": "string"}}, {"name": "message_id", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Deleted message"}, "403": error_response, "404": error_response}},
    }

    schemas = {
        "Error": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean", "example": False},
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "fields": {"type": "object", "additionalProperties": {"type": "string"}},
                    },
                },
            },
        },
        "Health": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "ok"},
                "database": {"type": "string", "example": "ok"},
                "schemaVersion": {"type": "string", "example": "2"},
                "time": {"type": "string", "format": "date-time"},
            },
        },
        "Session": {
            "type": "object",
            "properties": {
                "token": {"type": "string"},
                "user": {"$ref": ref("User")},
                "twoFactorRequired": {"type": "boolean"},
                "challengeToken": {"type": "string"},
            },
        },
        "Registration": {
            "type": "object",
            "properties": {
                "verificationRequired": {"type": "boolean"},
                "email": {"type": "string", "format": "email"},
            },
        },
        "User": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "initials": {"type": "string"},
                "role": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "emailVerified": {"type": "boolean"},
                "twoFactorEnabled": {"type": "boolean"},
                "memberSince": {"type": "string"},
                "points": {"type": "integer"},
            },
        },
        "Community": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "sport": {"type": "string"},
                "kind": {"type": "string"},
                "mark": {"type": "string"},
                "memberCount": {"type": "integer"},
                "joined": {"type": "boolean"},
                "joinRequestStatus": {"type": "string", "enum": ["pending", "approved", "denied"], "nullable": True},
                "pendingJoinRequestCount": {"type": "integer", "description": "Visible to community admins and super admins."},
                "role": {"type": "string", "nullable": True},
                "privacy": {"type": "string"},
                "accent": {"type": "string"},
                "description": {"type": "string"},
                "activity": {"type": "string"},
                "logoData": {"type": "string", "nullable": True},
                "bannerData": {"type": "string", "nullable": True},
            },
        },
        "Post": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "authorId": {"type": "string"},
                "author": {"type": "string"},
                "authorRole": {"type": "string"},
                "communityId": {"type": "string"},
                "text": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "liked": {"type": "boolean"},
                "likes": {"type": "integer"},
                "media": {"type": "object", "nullable": True},
                "comments": {"type": "array", "items": {"type": "object"}},
                "createdAt": {"type": "string", "format": "date-time"},
            },
        },
        "Poll": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "communityId": {"type": "string", "nullable": True},
                "question": {"type": "string"},
                "category": {"type": "string"},
                "author": {"type": "string"},
                "closesAt": {"type": "string", "format": "date-time"},
                "gameAt": {"type": "string", "format": "date-time", "nullable": True},
                "location": {"type": "string"},
                "feedbackDueAt": {"type": "string", "format": "date-time", "nullable": True},
                "feedbackCount": {"type": "integer"},
                "autoTeams": {"type": "object", "nullable": True},
                "canManageTeams": {"type": "boolean"},
                "yesPlayers": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "number": {"type": "integer"}, "position": {"type": "string"}, "rating": {"type": "number"}, "guest": {"type": "boolean"}}}},
                "noCount": {"type": "integer"},
                "guestCount": {"type": "integer"},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "votes": {"type": "integer"},
                        },
                    },
                },
                "userVote": {"type": "string", "nullable": True},
                "featured": {"type": "boolean"},
            },
        },
        "Duty": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "kind": {"type": "string", "enum": ["coffee", "donuts", "snacks", "drinks", "other"]},
                "kindLabel": {"type": "string"},
                "items": {"type": "array", "items": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["coffee", "donuts", "snacks", "drinks", "other"]}, "label": {"type": "string"}}}},
                "title": {"type": "string"},
                "startsAt": {"type": "string", "format": "date-time"},
                "note": {"type": "string"},
                "eventKey": {"type": "string", "nullable": True, "description": "Fixture or event id this duty is for."},
                "assignedTo": {"type": "object", "nullable": True, "description": "Community member responsible for this duty."},
                "claimedBy": {"type": "object", "nullable": True, "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "initials": {"type": "string"}, "tone": {"type": "string"}}},
                "claimedAt": {"type": "string", "format": "date-time", "nullable": True},
                "createdById": {"type": "string", "nullable": True},
            },
        },
        "DutyInput": {
            "type": "object",
            "required": ["community_id"],
            "anyOf": [{"required": ["kind", "starts_at"]}, {"required": ["items"]}],
            "properties": {
                "community_id": {"type": "string"},
                "kind": {"type": "string", "enum": ["coffee", "donuts", "snacks", "drinks", "other"]},
                "title": {"type": "string", "maxLength": 80},
                "starts_at": {"type": "string", "format": "date-time"},
                "note": {"type": "string", "maxLength": 200},
                "event_key": {"type": "string", "nullable": True},
                "assigned_to": {"type": "string", "nullable": True, "description": "A member of the selected community. Assigning another person requires community-admin access."},
                "items": {"type": "array", "minItems": 1, "maxItems": 10, "description": "For one duty, an array of item kind IDs such as coffee and donuts. A legacy batch of duty objects is also accepted.", "items": {"oneOf": [{"type": "string", "enum": ["coffee", "donuts", "snacks", "drinks", "other"]}, {"type": "object", "required": ["kind", "starts_at"], "properties": {"kind": {"type": "string", "enum": ["coffee", "donuts", "snacks", "drinks", "other"]}, "title": {"type": "string", "maxLength": 80}, "starts_at": {"type": "string", "format": "date-time"}, "note": {"type": "string", "maxLength": 200}, "event_key": {"type": "string", "nullable": True}, "assigned_to": {"type": "string", "nullable": True}}}]}},
            },
        },
        "CalendarEntry": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "source": {"type": "string", "enum": ["match", "event", "duty"]},
                "communityId": {"type": "string"},
                "communityName": {"type": "string", "description": "Present for duty entries."},
                "date": {"type": "string", "format": "date-time"},
                "title": {"type": "string"},
                "detail": {"type": "string"},
                "accent": {"type": "string", "enum": ["lime", "sky", "coral"]},
                "eventType": {"type": "string", "nullable": True},
                "duty": {"$ref": ref("Duty"), "nullable": True},
            },
        },
        "Player": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "number": {"type": "integer"},
                "pos": {"type": "string"},
                "group": {"type": "string"},
                "foot": {"type": "string"},
                "status": {"type": "string"},
                "rating": {"type": "number"},
                "ratingCount": {"type": "integer"},
                "userRating": {"type": "number", "nullable": True},
                "goals": {"type": "integer"},
                "assists": {"type": "integer"},
                "apps": {"type": "integer"},
                "dateOfBirth": {"type": "string", "format": "date", "nullable": True},
                "age": {"type": "integer", "nullable": True, "description": "Computed by the server from dateOfBirth."},
                "heightCm": {"type": "integer", "nullable": True},
                "bio": {"type": "string"},
                "imageData": {"type": "string", "nullable": True},
                "starts": {"type": "integer"},
                "minutes": {"type": "integer"},
                "yellowCards": {"type": "integer"},
                "redCards": {"type": "integer"},
                "cleanSheets": {"type": "integer"},
                "saves": {"type": "integer"},
                "registered": {"type": "boolean"},
                "isMine": {"type": "boolean", "description": "True when this player profile belongs to the authenticated member."},
            },
        },
        "PlayerUpdate": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "number": {"type": "integer"},
                "pos": {"type": "string"},
                "foot": {"type": "string"},
                "status": {"type": "string"},
                **PLAYER_PROFILE_FIELDS,
            },
        },
        "Team": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "formation": {"type": "string"},
                "startingXI": {"type": "array", "minItems": 11, "maxItems": 11, "items": {"oneOf": [{"type": "string"}, {"type": "null"}]}},
                "players": {"type": "array", "items": {"$ref": ref("Player")}},
            },
        },
        "Plan": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "communityId": {"type": "string", "nullable": True},
                "title": {"type": "string"},
                "opponent": {"type": "string"},
                "formation": {"type": "string"},
                "status": {"type": "string"},
                "checklist": {"type": "array", "items": {"type": "object"}},
                "board": {"type": "array", "items": {"type": "string"}},
            },
        },
        "Notification": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "icon": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "time": {"type": "string"},
                "unread": {"type": "boolean"},
                "route": {"type": "string"},
            },
        },
        "PickupResult": {
            "type": "object",
            "properties": {
                "teamA": {"type": "object"},
                "teamB": {"type": "object"},
                "floater": {"type": "object", "nullable": True},
                "gap": {"type": "number"},
                "positionGap": {"type": "integer"},
                "balanceScore": {"type": "integer"},
                "poolSize": {"type": "integer"},
                "sessionLabel": {"type": "string"},
            },
        },
        "Bootstrap": {
            "type": "object",
            "properties": {
                "version": {"type": "integer"},
                "serverTime": {"type": "string", "format": "date-time"},
                "user": {"$ref": ref("User")},
                "communities": {"type": "array", "items": {"$ref": ref("Community")}},
                "posts": {"type": "array", "items": {"$ref": ref("Post")}},
                "polls": {"type": "array", "items": {"$ref": ref("Poll")}},
                "teams": {"type": "array", "items": {"$ref": ref("Team")}},
                "plans": {"type": "array", "items": {"$ref": ref("Plan")}},
                "notifications": {"type": "array", "items": {"$ref": ref("Notification")}},
            },
        },
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Touchline API",
            "version": "1.0.0",
            "description": "REST API for the Touchline clubhouse. Browser sessions use Bearer tokens; external clients use an approved X-API-Key issued after super-admin review.",
            "contact": {"name": "Touchline"},
        },
        "servers": [{"url": "http://127.0.0.1:4173", "description": "Local development"}],
        "tags": [
            {"name": "Auth"},
            {"name": "Web app"},
            {"name": "Feed"},
            {"name": "Polls"},
            {"name": "Communities"},
            {"name": "Team"},
            {"name": "Game plans"},
            {"name": "Notifications"},
            {"name": "Pickup"},
            {"name": "Club"},
            {"name": "Demo"},
            {"name": "Public"},
        ],
        "paths": paths,
        "components": {
            "securitySchemes": {"BearerAuth": bearer, "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
            "schemas": schemas,
        },
        "security": [{"BearerAuth": []}, {"ApiKeyAuth": []}],
    }
