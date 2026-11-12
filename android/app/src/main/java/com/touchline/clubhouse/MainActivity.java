package com.touchline.clubhouse;

import android.os.Bundle;
import android.webkit.WebSettings;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Capacitor serves the local app from https://localhost by default.
        // Permit that page to call a private-LAN HTTP API during debug builds.
        // Release builds must use HTTPS and keep WebView mixed content blocked.
        if (BuildConfig.DEBUG && getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().getSettings()
                    .setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }
    }
}
