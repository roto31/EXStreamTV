import { useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Alert from "@mui/material/Alert";
import { usePersona } from "../context/PersonaContext";
import { captureSnapshot, revertSnapshot } from "../api/scheduleHistory";

export default function ScheduleHistoryPage() {
  const { personaId } = usePersona();
  const [channelIds, setChannelIds] = useState("");
  const [label, setLabel] = useState("");
  const [revertId, setRevertId] = useState("");
  const [msg, setMsg] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleCapture() {
    const ids = channelIds
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter(Number.isFinite);
    if (!ids.length) {
      setMsg({ kind: "error", text: "Enter at least one channel id." });
      return;
    }
    setBusy(true);
    try {
      const res = await captureSnapshot({ channel_ids: ids, persona_id: personaId, label: label || null });
      setMsg({ kind: "success", text: `Captured snapshot id ${res.id}` });
    } catch (e) {
      setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  async function handleRevert() {
    const hid = parseInt(revertId, 10);
    if (!Number.isFinite(hid)) {
      setMsg({ kind: "error", text: "Enter a valid history id." });
      return;
    }
    setBusy(true);
    try {
      const res = await revertSnapshot(hid, personaId);
      setMsg({ kind: "success", text: `Reverted ${res.items_restored ?? 0} items.` });
    } catch (e) {
      setMsg({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Schedule History
      </Typography>
      {msg && (
        <Alert severity={msg.kind} sx={{ mb: 2 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}
      <Stack spacing={3}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Capture Snapshot
            </Typography>
            <Stack spacing={2}>
              <TextField
                label="Channel IDs (comma-separated)"
                value={channelIds}
                onChange={(e) => setChannelIds(e.target.value)}
                size="small"
                fullWidth
              />
              <TextField
                label="Label (optional)"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                size="small"
                fullWidth
              />
              <Button
                variant="contained"
                onClick={handleCapture}
                disabled={busy}
                sx={{ alignSelf: "flex-start" }}
              >
                Capture
              </Button>
            </Stack>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Revert to Snapshot
            </Typography>
            <Stack spacing={2}>
              <TextField
                label="History ID"
                value={revertId}
                onChange={(e) => setRevertId(e.target.value)}
                size="small"
                sx={{ maxWidth: 200 }}
              />
              <Button
                variant="outlined"
                color="warning"
                onClick={handleRevert}
                disabled={busy}
                sx={{ alignSelf: "flex-start" }}
              >
                Revert
              </Button>
            </Stack>
          </CardContent>
        </Card>
      </Stack>
    </Box>
  );
}
