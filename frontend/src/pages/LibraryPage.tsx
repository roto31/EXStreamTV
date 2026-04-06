import { Link } from "react-router-dom";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Grid from "@mui/material/Grid";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardContent from "@mui/material/CardContent";
import MovieFilterIcon from "@mui/icons-material/MovieFilter";
import LiveTvIcon from "@mui/icons-material/LiveTv";

const sections = [
  { label: "Filler Lists", to: "/library/fillers", icon: <MovieFilterIcon fontSize="large" />, desc: "Short clips and bumpers used to fill gaps" },
  { label: "Custom Shows", to: "/library/custom-shows", icon: <LiveTvIcon fontSize="large" />, desc: "Manually curated show playlists" },
];

export default function LibraryPage() {
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Library
      </Typography>
      <Grid container spacing={3} sx={{ mt: 1 }}>
        {sections.map((s) => (
          <Grid key={s.to} size={{ xs: 12, sm: 6 }}>
            <Card>
              <CardActionArea component={Link} to={s.to}>
                <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                  {s.icon}
                  <Box>
                    <Typography variant="h6">{s.label}</Typography>
                    <Typography variant="body2" color="text.secondary">{s.desc}</Typography>
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
