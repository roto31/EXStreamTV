import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import { useHealth } from "../hooks/useQueryData";

export default function SystemPage() {
  const { data: health, isLoading, error } = useHealth();

  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        System
      </Typography>
      <Card>
        <CardContent>
          <Typography variant="overline" color="text.secondary">
            API Status
          </Typography>
          <Box sx={{ mt: 1 }}>
            {isLoading ? (
              <CircularProgress size={20} />
            ) : error ? (
              <Alert severity="error">
                {error instanceof Error ? error.message : String(error)}
              </Alert>
            ) : (
              <>
                <Chip label="API Online" color="success" size="small" />
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
              </>
            )}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
