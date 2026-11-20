// 원투원 LLM 게이트웨이 (Kotlin, Spring Boot WebFlux). 버전은 2026-11-20 Maven Central 최신 안정판
plugins {
    kotlin("jvm") version "2.4.21"
    kotlin("plugin.spring") version "2.4.21"
    id("org.springframework.boot") version "4.2.0"
    id("io.spring.dependency-management") version "1.1.7"
}

group = "taxsplit"
version = "0.1.0"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-webflux")
    // Boot 4부터 WebClient.Builder 자동 설정은 따로 나뉘었다
    implementation("org.springframework.boot:spring-boot-starter-webclient")
    implementation("org.jetbrains.kotlin:kotlin-reflect")
    implementation("org.yaml:snakeyaml")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
    testImplementation("com.squareup.okhttp3:mockwebserver3:5.5.1")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

kotlin {
    compilerOptions {
        freeCompilerArgs.addAll("-Xjsr305=strict")
    }
}

tasks.withType<Test> {
    useJUnitPlatform()
}
