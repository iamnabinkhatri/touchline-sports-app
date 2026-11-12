import test from "node:test";
import assert from "node:assert/strict";
import { groupNotifications } from "../js/notification-groups.js";

const post = (id, communityId, createdAt, unread = true) => ({
  id, communityId, createdAt, unread, kind: "post", route: `#/community/${communityId}/posts/${id}`,
});

test("post notifications are stacked by their own community and newest appears first", () => {
  const result = groupNotifications([
    post("a1", "club-a", "2026-11-11T10:00:00Z"),
    post("b1", "club-b", "2026-11-11T12:00:00Z"),
    post("a2", "club-a", "2026-11-11T13:00:00Z", false),
  ]);
  assert.deepEqual(result.stacks.map((stack) => stack.communityId), ["club-a", "club-b"]);
  assert.deepEqual(result.stacks[0].notifications.map((item) => item.id), ["a2", "a1"]);
  assert.equal(result.stacks[0].unreadCount, 1);
});

test("non-post notices remain independent and every excerpt retains its deep link", () => {
  const mention = { id: "m1", kind: "mention", unread: true, route: "#/community/club-a" };
  const result = groupNotifications([post("p1", "club-a", "2026-11-11T10:00:00Z"), mention]);
  assert.deepEqual(result.standalone, [mention]);
  assert.equal(result.stacks[0].notifications[0].route, "#/community/club-a/posts/p1");
});
