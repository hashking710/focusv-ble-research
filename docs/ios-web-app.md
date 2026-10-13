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

## Which device is which

focusv.app never uses Web Bluetooth's `device.id`. The V Browser and Bluefy are free to hand
the same device a new id on each pick, so a saved device would stop matching. Instead it reads
the **serial** from `user_data` characteristic `0x2A8A` ("First Name" in the spec, repurposed;
the model code is `0x2A90`). It keys everything on that serial:

- the saved device: Firestore `Devices/{uid}/{TYPE}/{serial}`;
- its presets: `Presets/{uid}/{TYPE}/{serial}/...`;
- the per-device documents (`Quantum/{serial}`, ...).

Registering a serial a second time gets "You've already registered this device!". Factory
placeholders (`00000000`, `22BA0001`, `23DA0001`, `A23DA0001`, `S23DA0001`, `S24DA0001`) are
treated as no serial.

**Terpline:** it reads `0x2A8A` on every connect and matches the saved device on
`serial:<serial>`. It falls back to `device.id` only for a placeholder or an unreadable serial.
A device saved under an old browser id is moved over to its serial on its next connect.

## Firmware update (OTA)

focusv.app's update screen (`UPDATE NOW`) does the following. It is the same wire format as
[the protocol reference](ble-protocol.md), and Terpline now matches it step for step.

1. **Before the button is pressed:** it fetches the image (`cache: 'no-store'`) and checks
   `KNLT` at bytes 8–11. It pads the image to a multiple of 16 bytes with `0xFF`, giving
   blocks = length / 16.
2. **Date and time:** it writes `77 0C yyyy(BE) M D h m 00 00 00 77` in UTC to the main write
   characteristic, then waits 350 ms.
3. **Start:** it waits a further 500 ms, writes `00 FF` and then `01 FF` to the OTA
   characteristic, and waits 300 ms.
4. **Blocks:** each block is `index(LE16) + 16 bytes + CRC-16/ARC(LE16)` over index + data.
   - Every write uses `writeValueWithoutResponse` when the characteristic allows it. Its write
     helper checks both `characteristic.writeWithoutResponse` (where The V Browser puts the
     flag) and `properties.writeWithoutResponse`.
   - With "new" firmware it reads the OTA characteristic back after every 8th block; that read
     is the flow control. Without it, it leaves a 5 ms gap after every block. "New" means a
     Carta 2 software revision dated 06/20/22 or later, or any Aeris or Sport.
   - On a Carta 2 dated 04/11/23 or later it sends `A4 04 pct A4` to the main characteristic
     whenever the percentage changes (never 0 or 100). The device shows it on screen.
5. **End:** it writes `02 FF + (blocks-1)(LE16) + ~(blocks-1)(LE16)`. With "new" firmware the
   message is "Update complete! Rebooting device..", otherwise "Applying update.. This may
   take a minute..".
6. **Around the update:**
   - It takes a screen wake lock (`navigator.wakeLock.request('screen')`) and takes it again on
     every `visibilitychange` back to visible.
   - Leaving the screen is blocked.
   - Its stated install time is "2-4 minutes", with the warning "Please do not turn off your
     device, or close the app!".

The date is read from the software revision `PROD-MMDDYY`. Before matching this, Terpline wrote
every block with a response and paced it only by an 8 ms gap. That works in Chrome but not with
the write-without-response pacing The V Browser is built around.
