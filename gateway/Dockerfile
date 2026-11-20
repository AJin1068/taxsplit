# 원투원 LLM 게이트웨이 이미지. 빌드는 JDK 21 + Gradle wrapper, 실행은 JRE 21만
FROM gradle:jdk21 AS build
WORKDIR /src
COPY gradlew settings.gradle.kts build.gradle.kts ./
COPY gradle ./gradle
# 의존성을 먼저 받아 소스만 바뀔 때 다시 받지 않는다
RUN ./gradlew dependencies --no-daemon -q > /dev/null
COPY src ./src
# 테스트는 레포 루트의 에이전트 단가표도 읽어서 여기서는 돌리지 않는다 (gateway/README.md 참고)
RUN ./gradlew bootJar -x test --no-daemon -q

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/build/libs/*.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
