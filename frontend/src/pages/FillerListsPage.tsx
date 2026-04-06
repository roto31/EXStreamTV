import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";

export default function FillerListsPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Filler Lists
      </Typography>
      <Alert severity="info">
        Filler list management will be available in a future update.
      </Alert>
    </Box>
  );
}
