# Touchline mobile apps

Touchline's iOS and Android clients are Capacitor apps that bundle the same responsive web UI and call the same `/api/v1` server as the browser app. That keeps communities, messages, polls, team changes, schedules and account sessions shared through the existing database. There is no second mobile database or parallel set of business rules.

The mobile bundle contains only `index.html`, `styles.css`, `styles/` and `js/`. It does not copy `.env`, the backend, or `data/touchline.db`.

## Prepare and add the native projects

Requires Node 20+, Xcode and CocoaPods for iOS, and Android Studio with an Android SDK for Android. The iOS deployment target is 15.0, supporting iPhone 11 through current iPhone models that run iOS 15 or newer. The generated Android target is API 23+. The project uses Capacitor 7 to match the Node 20 runtime currently used by this repository. Use Android Studio's **Embedded JDK** for Gradle; newer standalone Java versions may be too new for the generated Android Gradle plugin.

```sh
npm install
npm run mobile:prepare
npm run mobile:add:ios
npm run mobile:add:android
npm run mobile:sync
```

`mobile:add:*` is a one-time step per platform. When the web app changes, run `npm run mobile:sync` to refresh the native app bundle and native plugin dependencies.

## Connect to the same server

Start the existing backend. On first app launch, enter its origin (scheme, host and optional port, without `/api/v1`). For local Wi-Fi testing, bind the backend to the network and enter the computer's LAN address from the phone, for example `http://192.168.1.20:4173`:

```sh
HOST=0.0.0.0 npm start
```

The mobile client checks `GET /api/v1/health` before continuing. Both phone and computer must be on a network that can reach the server. Local HTTP is accepted only for loopback, private IPv4, `.local` and `.lan` hosts. Use HTTPS for any internet server or release build.

The API's default CORS allowlist includes the Capacitor WebView origins (`capacitor://localhost`, `http://localhost`, and `https://localhost`). If `TOUCHLINE_CORS_ORIGINS` is explicitly set in the server environment, include the platform origins in that comma-separated allowlist as well.

To change the server later, sign out and choose **Server connection** on the sign-in screen. **Super admin sign in** switches to the separate admin authentication flow; the API still checks the configured super-admin credentials and role.

## Check the iOS app

1. In a terminal, start the API server so a device can reach it:

   ```sh
   HOST=0.0.0.0 npm start
   ```

2. In another terminal, build and sync the latest UI into the iOS project:

   ```sh
   npm run mobile:sync
   npm run mobile:open:ios
   ```

3. In Xcode, select an iPhone simulator or connected iPhone and press **Run**. If using a real phone, accept the local-network access prompt when testing against a computer on Wi-Fi.

4. On first launch, enter the API server origin. Use `http://127.0.0.1:4173` in the simulator or `http://<Mac-LAN-IP>:4173` on a physical phone. Do not add `/api/v1`; the app checks `/api/v1/health` itself.

5. Sign in as a member, then check that a poll, community post, chat message, or calendar entry is visible in the web app after refreshing it. Sign out and use **Super admin sign in** to check the administrator flow.

For a local device build from the terminal, the generated workspace is `ios/App/App.xcworkspace`. To compile for the oldest requested model and a current model using the installed simulator runtime, select **iPhone 11** and **iPhone 17** destinations in Xcode. One iOS app build supports all compatible iPhone sizes; it does not require a separate binary for each model. For an App Store archive, select **Any iOS Device** in Xcode and use **Product → Archive**; configure your Apple signing team first.

## Check the Android app

1. Open Android Studio's SDK Manager and install Android SDK Platform 35 and Android SDK Build Tools 35. In **Settings → Build, Execution, Deployment → Build Tools → Gradle**, set **Gradle JDK** to **Embedded JDK**. The generated Gradle build does not work with the Java 25 runtime currently selected by this computer.

2. Start the API server in a terminal:

   ```sh
   HOST=0.0.0.0 npm start
   ```

3. Build and open the Android project:

   ```sh
   npm run mobile:sync
   npm run mobile:open:android
   ```

4. In Android Studio, create or select an emulator (or connect a phone), wait for Gradle sync, then press **Run**. For an emulator, use `http://10.0.2.2:4173` as the API server origin. For a physical phone, use `http://<Mac-LAN-IP>:4173`.

   For a physical phone on home Wi-Fi, use the **debug** app build for HTTP testing. The debug build allows the Capacitor HTTPS WebView to call a private-LAN HTTP API. Rebuild and reinstall it after changing native settings. Release builds keep mixed content blocked and must use an HTTPS API server.

5. Sign in and repeat the same shared-data checks used on iOS. Create or update a harmless test item in the mobile app and confirm it appears in the web app and on the other platform.

From a terminal with Android Studio's Embedded JDK and Android SDK configured, the debug APK can also be built with:

```sh
cd android
./gradlew assembleDebug
```

For a Play Store release, use Android Studio's **Build → Generate Signed Bundle / APK** and create a signed Android App Bundle. Release API servers must use HTTPS; the Android project allows cleartext HTTP only for debug builds.

## Full smoke-test checklist

- Start with a reachable server and verify the app proceeds past its connection screen; stop the server and confirm it shows a recoverable connection error.
- Sign in as a member, sign out, sign in as super admin, then sign out and return to member sign-in.
- Check community feed, image upload, chat send/edit/delete, poll create/vote, calendar duties, team hub, starting XI and game plans.
- Verify a change from iOS appears in Android and the web app, then verify a change from the web app appears in each mobile app after refresh.
- Check registration/email verification, forgot-password email, and 2FA with working SMTP and the production auth settings.
- Run frontend, backend and mobile bundle tests:

  ```sh
  npm run test:frontend
  npm run test:backend
  npm run mobile:prepare
  ```

The mobile UI is the same code as the web UI, so the frontend suite covers shared rendering and behavior. Backend tests exercise the API contract used by all clients.

Before release, set the app to an HTTPS server, verify its CORS allowlist and SMTP settings, set production signing credentials in the IDE, and run the test suites. The app uses the server's existing registration, email verification, password recovery, 2FA, role checks and approved API-key rules.

## Verification

```sh
npm test
npm run mobile:prepare
```

`npm test` runs the frontend suite and backend API/security suite. `mobile:prepare` validates that a clean native web bundle can be generated from the app source.
