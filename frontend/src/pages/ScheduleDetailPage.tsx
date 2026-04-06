import { Link, useParams } from "react-router-dom";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import Chip from "@mui/material/Chip";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import MuiLink from "@mui/material/Link";
import { useSchedule } from "../hooks/useQueryData";

export default function ScheduleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const numId = id ? Number.parseInt(id, 10) : NaN;

  const { data: schedule, isLoading, error } = useSchedule(numId);

  if (!Number.isFinite(numId))
    return <Alert severity="error">Invalid schedule id.</Alert>;
  if (isLoading) return <CircularProgress />;
  if (error)
    return (
      <Alert severity="error">
        {error instanceof Error ? error.message : String(error)}
      </Alert>
    );
  if (!schedule) return null;

  return (
    <Box>
      <MuiLink component={Link} to="/schedules" underline="hover">
        ← Schedules
      </MuiLink>
      <Typography variant="h4" fontWeight={700} sx={{ mt: 2 }}>
        {schedule.name ?? `Schedule ${schedule.id}`}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        id {schedule.id}
      </Typography>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="overline" color="text.secondary">
            Options
          </Typography>
          <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 1 }}>
            {schedule.shuffle_schedule_items && (
              <Chip label="Shuffle items" size="small" />
            )}
            {schedule.random_start_point && (
              <Chip label="Random start" size="small" />
            )}
            {schedule.keep_multi_part_episodes_together && (
              <Chip label="Keep multi-part together" size="small" />
            )}
            {schedule.treat_collections_as_shows && (
              <Chip label="Collections as shows" size="small" />
            )}
            {schedule.is_yaml_source && (
              <Chip label="YAML source" size="small" variant="outlined" />
            )}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
