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
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import MuiLink from "@mui/material/Link";
import { useSchedules } from "../hooks/useQueryData";

export default function SchedulesPage() {
  const { data: rows, isLoading, error } = useSchedules();

  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Schedules
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
            {rows?.length ?? 0} schedule(s)
          </Typography>
          <TableContainer component={Paper} sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Name</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows?.map((s) => (
                  <TableRow key={s.id} hover>
                    <TableCell sx={{ fontFamily: "monospace" }}>{s.id}</TableCell>
                    <TableCell>
                      <MuiLink component={Link} to={`/schedules/${s.id}`} underline="hover">
                        {s.name ?? `Schedule ${s.id}`}
                      </MuiLink>
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
