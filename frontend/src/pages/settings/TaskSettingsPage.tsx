import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";

export default function TaskSettingsPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Settings — Background Tasks
      </Typography>
      <Alert severity="info">
        Background task scheduling and monitoring will be available in a future update.
      </Alert>
    </Box>
  );
}
