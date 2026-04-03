/**
 * Track B — React shell (EXStreamTV-UI-Architecture.md).
 * Phase 0: ErsatzTV client files in the spec paths were not present in this repo;
 * extend with Tailwind, personas, and v1 API clients per the architecture doc.
 */
export default function App() {
  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem", maxWidth: 640 }}>
      <h1>EXStreamTV</h1>
      <p>
        Frontend scaffold. Run the FastAPI app on port 8000 and{" "}
        <code>npm run dev</code> here; API is proxied under <code>/api</code> and{" "}
        <code>/iptv</code>.
      </p>
    </main>
  );
}
