import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  {
    rules: {
      // No raw console.log in production code (warn is ok for debugging)
      "no-console": ["warn", { allow: ["warn", "error"] }],
      // Catch missing deps in hooks early
      "react-hooks/exhaustive-deps": "error",
      // Discourage any-casting
      "@typescript-eslint/no-explicit-any": "warn",
      // No unused vars (underscore prefix exempted)
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
]);

export default eslintConfig;
