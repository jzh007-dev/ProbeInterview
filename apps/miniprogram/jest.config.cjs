module.exports = {
  clearMocks: true,
  setupFilesAfterEnv: ["<rootDir>/tests/setup.cjs"],
  testEnvironment: "jsdom",
  testMatch: ["<rootDir>/tests/**/*.test.cjs"],
  transform: {
    "^.+\\.ts$": [
      "ts-jest",
      {
        tsconfig: {
          module: "CommonJS",
          target: "ES2022",
        },
      },
    ],
  },
}
