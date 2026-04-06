import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Alert from "@mui/material/Alert";

export default function GuidePage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        TV Guide
      </Typography>
      <Alert severity="info" sx={{ mb: 3 }}>
        EPG grid view is coming soon. Channel guide data is served via the XMLTV endpoint.
      </Alert>
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary">
            Access your M3U playlist at{" "}
            <code>/iptv/playlist.m3u</code> and XMLTV guide at{" "}
            <code>/iptv/xmltv.xml</code>.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
