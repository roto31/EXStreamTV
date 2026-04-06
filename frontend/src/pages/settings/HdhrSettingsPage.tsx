import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";

export default function HdhrSettingsPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Settings — HDHomeRun
      </Typography>
      <Alert severity="info">
        HDHomeRun emulation settings will be available in a future update.
      </Alert>
    </Box>
  );
}
