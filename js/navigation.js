export function baseHrefForPath(pathname) {
  return pathname && pathname !== "/" && pathname !== "/index.html" ? pathname : "/";
}

