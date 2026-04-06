import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";

export default function XmltvSettingsPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Settings — XMLTV
      </Typography>
      <Alert severity="info">
        XMLTV output configuration (programme offset, cache TTL) will be available in a future update.
      </Alert>
    </Box>
  );
}
