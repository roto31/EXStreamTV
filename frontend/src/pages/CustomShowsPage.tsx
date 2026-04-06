import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";

export default function CustomShowsPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Custom Shows
      </Typography>
      <Alert severity="info">
        Custom show management will be available in a future update.
      </Alert>
    </Box>
  );
}
