import { Link } from "react-router-dom";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import Chip from "@mui/material/Chip";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import MuiLink from "@mui/material/Link";
import { useHealth } from "../hooks/useQueryData";

export default function Dashboard() {
  const { data: health, isLoading, error } = useHealth();

  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Start the API on port{" "}
        <code>8411</code> then run{" "}
        <code>npm run dev</code> in the frontend.
      </Typography>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="overline" color="text.secondary">
            API Health
          </Typography>
          {isLoading ? (
            <Box sx={{ mt: 1 }}>
              <CircularProgress size={20} />
            </Box>
          ) : error ? (
            <Alert severity="warning" sx={{ mt: 1 }}>
              {error instanceof Error ? error.message : String(error)}
            </Alert>
          ) : (
            <Box sx={{ mt: 1 }}>
              <Chip label="Connected" color="success" size="small" />
              <Box
                component="pre"
                sx={{
                  mt: 2,
                  p: 2,
                  borderRadius: 1,
                  bgcolor: "action.hover",
                  overflowX: "auto",
                  fontSize: "0.75rem",
                }}
              >
                {JSON.stringify(health, null, 2)}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      <Grid container spacing={2} sx={{ mt: 2 }}>
        {[
          { label: "Channels", to: "/channels" },
          { label: "Schedules", to: "/schedules" },
          { label: "Schedule History", to: "/schedule-history" },
          { label: "TV Guide", to: "/guide" },
        ].map((item) => (
          <Grid key={item.to} size={{ xs: 6, sm: 3 }}>
            <Card>
              <CardContent>
                <MuiLink component={Link} to={item.to} underline="hover">
                  {item.label}
                </MuiLink>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
