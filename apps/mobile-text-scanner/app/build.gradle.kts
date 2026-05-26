plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.newera.mobiletextscanner"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.newera.mobiletextscanner"
        minSdk = 23
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")

    // Bundled Latin Text Recognition v2 model for reliable first-run demos.
    implementation("com.google.mlkit:text-recognition:16.0.1")
}
