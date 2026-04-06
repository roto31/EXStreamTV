import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";

export default function FfmpegSettingsPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Settings — FFmpeg
      </Typography>
      <Alert severity="info">
        FFmpeg configuration (executable path, hardware acceleration, default bitrate) will be available in a future update.
      </Alert>
    </Box>
  );
}
