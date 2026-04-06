import { Link } from "react-router-dom";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import MuiLink from "@mui/material/Link";
import { useChannels } from "../hooks/useQueryData";

export default function ChannelsPage() {
  const { data: rows, isLoading, error } = useChannels();

  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Channels
      </Typography>

      {isLoading ? (
        <CircularProgress />
      ) : error ? (
        <Alert severity="error">
          {error instanceof Error ? error.message : String(error)}
        </Alert>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {rows?.length ?? 0} channel(s)
          </Typography>
          <TableContainer component={Paper} sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Group</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows?.map((c) => (
                  <TableRow key={c.id} hover>
                    <TableCell sx={{ fontFamily: "monospace" }}>
                      {c.number ?? c.id}
                    </TableCell>
                    <TableCell>
                      <MuiLink component={Link} to={`/channels/${c.id}`} underline="hover">
                        {c.name ?? `Channel ${c.id}`}
                      </MuiLink>
                    </TableCell>
                    <TableCell>{c.group ?? "—"}</TableCell>
                    <TableCell>
                      <Chip
                        label={c.enabled === false ? "Disabled" : "Active"}
                        color={c.enabled === false ? "default" : "success"}
                        size="small"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Box>
  );
}
