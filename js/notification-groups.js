export function groupNotifications(notifications = []) {
  const groups = new Map();
  const standalone = [];
  for (const notification of notifications) {
    if (notification.kind !== "post" || !notification.communityId) {
      standalone.push(notification);
      continue;
    }
    if (!groups.has(notification.communityId)) {
      groups.set(notification.communityId, { communityId: notification.communityId, notifications: [] });
    }
    groups.get(notification.communityId).notifications.push(notification);
  }
  const stacks = [...groups.values()];
  for (const stack of stacks) {
    stack.notifications.sort((a, b) => Date.parse(b.createdAt || 0) - Date.parse(a.createdAt || 0));
    stack.unreadCount = stack.notifications.filter((notification) => notification.unread).length;
    stack.latestAt = stack.notifications[0]?.createdAt || "";
  }
  stacks.sort((a, b) => Date.parse(b.latestAt || 0) - Date.parse(a.latestAt || 0));
  standalone.sort((a, b) => Date.parse(b.createdAt || 0) - Date.parse(a.createdAt || 0));
  return { stacks, standalone };
}
