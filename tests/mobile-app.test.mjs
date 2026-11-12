import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const root = new URL("../", import.meta.url);
const read = (path) => readFileSync(new URL(path, root), "utf8");

test("mobile bundle builds only the shared app UI and never packages server secrets or database files", () => {
  const build = spawnSync(process.execPath, ["scripts/build-mobile.mjs"], { cwd: new URL("..", import.meta.url), encoding: "utf8" });
  assert.equal(build.status, 0, build.stderr || build.stdout);
  const output = new URL("../mobile/www/", import.meta.url);
  assert.ok(existsSync(new URL("index.html", output)));
  assert.ok(existsSync(new URL("js/app.js", output)));
  assert.ok(existsSync(new URL("styles.css", output)));
  assert.ok(existsSync(new URL("mobile-entry.js", output)));
  assert.equal(existsSync(new URL(".env", output)), false);
  assert.equal(existsSync(new URL("data/touchline.db", output)), false);
  assert.match(read("mobile/www/index.html"), /src="mobile-entry\.js"/);
});

test("mobile client uses the configured server API origin and keeps web as the default", () => {
  assert.match(read("js/api.js"), /globalThis\.window\?\.TOUCHLINE_API_BASE\s*\|\|\s*"\/api\/v1"/);
  const entry = read("mobile/mobile-entry.js");
  assert.match(entry, /touchline:mobile-api-origin/);
  assert.match(entry, /\/api\/v1\/health/);
  assert.match(entry, /localStorage\.setItem\(API_ORIGIN_KEY, origin\)/);
  assert.match(entry, /https:/);
  assert.match(entry, /http:/);
});

test("native mobile auth exposes member sign-in without a super-admin entry", () => {
  const app = read("js/app.js");
  assert.match(app, /TOUCHLINE_MOBILE[\s\S]*mobileConfigure/);
  assert.doesNotMatch(app, /mobileAdmin/);
  assert.match(app, /Super-admin access is available only in the web app/);
  const nativeLoginLinks = app.slice(app.indexOf("${window.TOUCHLINE_MOBILE ? `<div class=\"auth-links\""), app.indexOf(" : \"\"}", app.indexOf("${window.TOUCHLINE_MOBILE ? `<div class=\"auth-links\"")));
  assert.doesNotMatch(nativeLoginLinks, /Super admin/i);
  assert.match(app, /Server connection/);
  const config = JSON.parse(read("capacitor.config.json"));
  assert.equal(config.appId, "com.touchline.clubhouse");
  assert.equal(config.webDir, "mobile/www");
});

test("backend explicitly allows Capacitor WebView origins for same-API mobile access", () => {
  const config = read("backend/config.py");
  assert.match(config, /capacitor:\/\/localhost,http:\/\/localhost,https:\/\/localhost/);
});

test("iOS app adopts UIScene lifecycle required by current iOS SDKs", () => {
  const plist = read("ios/App/App/Info.plist");
  const sceneDelegate = read("ios/App/App/SceneDelegate.swift");
  const project = read("ios/App/App.xcodeproj/project.pbxproj");
  assert.match(plist, /UIApplicationSceneManifest/);
  assert.match(plist, /\$\(PRODUCT_MODULE_NAME\)\.SceneDelegate/);
  assert.match(plist, /UISceneStoryboardFile[\s\S]*?<string>Main<\/string>/);
  assert.match(sceneDelegate, /UIWindowSceneDelegate/);
  assert.match(project, /SceneDelegate\.swift in Sources/);
});

test("iOS CocoaPods embed phase is compatible with macOS script execution", () => {
  const project = read("ios/App/App.xcodeproj/project.pbxproj");
  const podfile = read("ios/App/Podfile");
  const frameworksScript = read("ios/App/Pods/Target Support Files/Pods-App/Pods-App-frameworks.sh");
  assert.equal((project.match(/ENABLE_USER_SCRIPT_SANDBOXING = NO;/g) || []).length, 2);
  assert.match(podfile, /realpath -mq[\s\S]*?realpath -q/);
  assert.match(podfile, /line\.start_with\?\('mkdir -p '\)/);
  assert.match(frameworksScript, /^\/bin\/mkdir -p "\$\{CONFIGURATION_BUILD_DIR\}/m);
});
