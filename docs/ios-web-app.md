# focusv.app on iPhone: The V Browser integration

How the official web app (focusv.app, an Expo / React Native Web build) handles iOS, read from
its live bundle (`/_expo/static/js/web/AppEntry-1545243a71494d95254e56bb57d4c59d.js`, checked
2026-10-13), and how Terpline matches it.

## The V Browser

- App Store id6446792641, bundle `com.v.browser`, seller V Technologies. It is a WKWebView browser
  with Web Bluetooth. Its user agent carries `V Browser/1.0.0` or `V Browser/1.1.0`.
- It puts a non-standard `window.requestFullscreen` / `window.exitFullscreen` on `window`, and
  `navigator.notifications` (`status()`, used by focusv.app for push tokens).
- No URL scheme or associated-domains file was found. The only way to get an icon that opens in it
  is through its own bottom-bar **Share** button → add to home screen.

## What focusv.app does

| Area | focusv.app |
|---|---|
| Browser check (on mount) | If the UA has `V Browser` or `Chrome`, then for `V Browser` && `!navigator.standalone` && Fullscreen setting off it shows **Fullscreen Shortcut**. In every other browser (Safari, Firefox, Bluefy, iOS Chrome "CriOS") it shows **Browser Compatibility**. |
| Browser Compatibility | Dismissable (backdrop), in memory only. "For the best experience, please use our newest iOS app: V Browser." It shows a V Browser icon (100×100, radius 20), then "Remember to navigate to:" over an image of the address, then a bold 12 px line: "We'll automatically copy the link for easy access!". Its **Go to the App Store** button runs `clipboard.writeText("https://focusv.app")` and then opens the App Store page. |
| Fullscreen Shortcut | Not dismissable. Its only action is **IGNORE**, kept in memory. "We recommend creating a fullscreen shortcut by tapping the button at the bottom of your screen." It shows a picture of The V Browser's bottom bar with the Share button boxed in teal. There is one picture per version: 1.0.0 is back, forward, reload, share, bookmarks, +; 1.1.0 is back, forward, share, star, bookmarks. The version is 1.0.0 unless the UA says 1.1.0. |
| Fullscreen setting | `localStorage.fullscreenMode` (default off). It calls `window.requestFullscreen()` / `exitFullscreen()` at each launch. Shown (settings toggle and header icon) only when `window.requestFullscreen` exists and the page isn't standalone. When on, the shortcut dialog is hidden. |
| Offline | A "Connection Error" dialog: "You must be connected to the internet to continue". Not dismissable while offline. |
| Status bar | `apple-mobile-web-app-status-bar-style` is rewritten when the theme changes (`default` / `black-translucent`). |
| Head | viewport `width=device-width,initial-scale=1,minimum-scale=1,maximum-scale=1.00001,viewport-fit=cover`. `mobile-web-app-capable`, `apple-mobile-web-app-capable` and `apple-touch-fullscreen` are all `yes`, plus title and status bar. `apple-touch-icon` is 180×180. It has 10 `apple-touch-startup-image` links (iPhone SE through iPad Pro). No web manifest. |
| Bluetooth picker | CARTA: `filters [{name:'CARTA'}]`. Carta 2 / Aeris / Sport: `filters [{services:[1011123e-8535-b5a0-7140-a304d2495cb7]}, {services:[0x180a]}]`. optionalServices are the Carta service, the OTA service, `device_information`, `user_data` and `battery_service`. |
| After connecting | It reads `device_information.software_revision_string`, `user_data` (model code; 0x2A90), and `battery_service` char 0x2BEC (optional). It listens for `gattserverdisconnected`. |

## Terpline

| Area | Terpline | Difference |
|---|---|---|
| Browser check, both dialogs | Same triggers and same wording. Terpline draws its own picture of the toolbar instead of using Focus V's. | IGNORE / dismiss last the browsing session rather than in-memory state, because Terpline's sign-in is a full-page redirect and focusv.app never reloads. |
| Launch from the icon | The Fullscreen setting hides the dialog, as in focusv.app. | The V Browser's shortcut opens a non-standalone tab, so the address carries `#from-home` while the dialog is up. An icon made then keeps the tag, and a later launch from it marks the shortcut as made. |
| Fullscreen setting | The same, in the header (⛶) and on the account page. | — |
| Offline, status bar, head | The same. | Splash screens also cover the current iPhones (360×780 through 440×956 @3x) that focusv.app's list misses. There is a web manifest for Chrome / Edge / Android installs. |
| Bluetooth picker | In The V Browser: focusv.app's filters, plus an offer of the unfiltered list if nothing was picked. Everywhere else (Bluefy, Chrome, Edge, ...): `acceptAllDevices`. | Bluefy's service-UUID filtering is broken, so it is never used outside The V Browser. |
| After connecting | Software revision and model code, the same reads. | The battery characteristic isn't read, because the vape protocol already reports state. Push notifications (`navigator.notifications`) aren't used. |
