import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Grid from "@mui/material/Grid";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";

const sourceTypes = [
  { label: "Plex", description: "Connect a Plex Media Server", status: "supported" },
  { label: "Jellyfin", description: "Connect a Jellyfin server", status: "supported" },
  { label: "Emby", description: "Connect an Emby server", status: "planned" },
  { label: "Local Files", description: "Add local media directories", status: "planned" },
];

export default function SourcesPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Media Sources
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Configure media server connections for channel programming.
      </Typography>
      <Grid container spacing={3} sx={{ mt: 1 }}>
        {sourceTypes.map((s) => (
          <Grid key={s.label} size={{ xs: 12, sm: 6 }}>
            <Card>
              <CardContent sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <Box>
                  <Typography variant="h6">{s.label}</Typography>
                  <Typography variant="body2" color="text.secondary">{s.description}</Typography>
                </Box>
                <Chip
                  label={s.status}
                  color={s.status === "supported" ? "success" : "default"}
                  size="small"
                />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
