import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Chip from "@mui/material/Chip";
import MuiLink from "@mui/material/Link";
import Button from "@mui/material/Button";
import {
  useChannel,
  useChannelPlayouts,
  useNowPlaying,
  usePlayoutItems,
} from "../hooks/useQueryData";
import type { ChannelPlayoutRow } from "../api/playouts";

function pickPrimary(rows: ChannelPlayoutRow[]): ChannelPlayoutRow | null {
  if (!rows.length) return null;
  return rows.find((p) => p.is_active) ?? rows[0];
}

export default function ChannelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const numId = id ? Number.parseInt(id, 10) : NaN;
  const [tab, setTab] = useState(0);
  const [showRaw, setShowRaw] = useState(false);

  const { data: row, isLoading: rowLoading, error: rowError } = useChannel(numId);
  const { data: playouts } = useChannelPlayouts(numId);
  const primaryPlayout = useMemo(
    () => (playouts ? pickPrimary(playouts) : null),
    [playouts]
  );
  const { data: nowPlaying } = useNowPlaying(primaryPlayout?.id);
  const { data: timeline } = usePlayoutItems(primaryPlayout?.id);

  if (!Number.isFinite(numId)) {
    return <Alert severity="error">Invalid channel id.</Alert>;
  }
  if (rowLoading) return <CircularProgress />;
  if (rowError) {
    return (
      <Alert severity="error">
        {rowError instanceof Error ? rowError.message : String(rowError)}
      </Alert>
    );
  }
  if (!row) return null;

  return (
    <Box>
      <MuiLink component={Link} to="/channels" underline="hover">
        ← Channels
      </MuiLink>
      <Typography variant="h4" fontWeight={700} sx={{ mt: 2 }}>
        {row.name ?? `Channel ${row.id}`}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        #{row.number ?? "—"} · id {row.id}
        {row.enabled === false ? " · disabled" : ""}
      </Typography>

      <Tabs value={tab} onChange={(_e, v: number) => setTab(v)} sx={{ mt: 3 }}>
        <Tab label="Properties" />
        <Tab label="Programming" />
        <Tab label="JSON" />
      </Tabs>

      {tab === 0 && (
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="overline" color="text.secondary">
              Playouts
            </Typography>
            {!playouts ? (
              <CircularProgress size={20} sx={{ ml: 1 }} />
            ) : playouts.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                No playouts for this channel.
              </Typography>
            ) : (
              <TableContainer sx={{ mt: 1 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Active</TableCell>
                      <TableCell>Schedule</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {playouts.map((p) => (
                      <TableRow
                        key={p.id}
                        selected={primaryPlayout?.id === p.id}
                      >
                        <TableCell sx={{ fontFamily: "monospace" }}>
                          {p.id}
                        </TableCell>
                        <TableCell>{p.playout_type ?? "—"}</TableCell>
                        <TableCell>
                          <Chip
                            label={p.is_active ? "Active" : "Inactive"}
                            color={p.is_active ? "success" : "default"}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>{p.program_schedule_id ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 1 && (
        <Box sx={{ mt: 2 }}>
          {primaryPlayout && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Card>
                  <CardContent>
                    <Typography variant="overline" color="text.secondary">
                      Now Playing
                    </Typography>
                    {!nowPlaying ? (
                      <CircularProgress size={20} />
                    ) : nowPlaying.current ? (
                      <Box sx={{ mt: 1 }}>
                        <Typography fontWeight={600}>
                          {nowPlaying.current.title ?? "Untitled"}
                        </Typography>
                        {nowPlaying.current.episode_title && (
                          <Typography variant="body2" color="text.secondary">
                            {nowPlaying.current.episode_title}
                          </Typography>
                        )}
                        {nowPlaying.current.progress_seconds != null && (
                          <Typography variant="caption" color="text.secondary">
                            {Math.round(nowPlaying.current.progress_seconds)}s /{" "}
                            {Math.round(nowPlaying.current.duration_seconds ?? 0)}s
                          </Typography>
                        )}
                      </Box>
                    ) : (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Nothing playing
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Card>
                  <CardContent>
                    <Typography variant="overline" color="text.secondary">
                      Up Next
                    </Typography>
                    {nowPlaying?.next ? (
                      <Box sx={{ mt: 1 }}>
                        <Typography fontWeight={600}>
                          {nowPlaying.next.title ?? "Untitled"}
                        </Typography>
                        {nowPlaying.next.starts_in_seconds != null && (
                          <Typography variant="caption" color="text.secondary">
                            in {Math.round(nowPlaying.next.starts_in_seconds)}s
                          </Typography>
                        )}
                      </Box>
                    ) : (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        —
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}

          {timeline && timeline.items.length > 0 && (
            <Card sx={{ mt: 2 }}>
              <CardContent>
                <Typography variant="overline" color="text.secondary">
                  Upcoming ({timeline.count} items)
                </Typography>
                <Box sx={{ maxHeight: 300, overflowY: "auto", mt: 1 }}>
                  {timeline.items.map((it) => (
                    <Box
                      key={it.id}
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        py: 0.5,
                        borderBottom: "1px solid",
                        borderColor: "divider",
                      }}
                    >
                      <Typography variant="body2">
                        {it.title ?? it.custom_title ?? `Item ${it.id}`}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ fontFamily: "monospace" }}
                      >
                        {it.start_time}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          )}
        </Box>
      )}

      {tab === 2 && (
        <Box sx={{ mt: 2 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={() => setShowRaw((v) => !v)}
          >
            {showRaw ? "Hide" : "Show"} raw JSON
          </Button>
          {showRaw && (
            <Paper sx={{ mt: 2, p: 2 }}>
              <Box
                component="pre"
                sx={{ overflowX: "auto", fontSize: "0.75rem", m: 0 }}
              >
                {JSON.stringify(row, null, 2)}
              </Box>
            </Paper>
          )}
        </Box>
      )}
    </Box>
  );
}
