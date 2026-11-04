import com.epam.parso.Column;
import com.epam.parso.SasFileProperties;
import com.epam.parso.SasFileReader;
import com.epam.parso.impl.SasFileReaderImpl;
import java.io.FileInputStream;

/** Lit un .sas7bdat avec Parso et affiche : "#META nom|type|longueur|label|format" par colonne, "#ROWS n", puis une ligne TSV par ligne. */
public class ParsoDump {
    public static void main(String[] a) throws Exception {
        try (FileInputStream in = new FileInputStream(a[0])) {
            SasFileReader r = new SasFileReaderImpl(in);
            SasFileProperties p = r.getSasFileProperties();
            for (Column c : r.getColumns()) {
                System.out.println("#META\t" + c.getName() + "\t" + c.getType().getSimpleName() + "\t" + c.getLength() + "\t" + c.getLabel() + "\t" + c.getFormat());
            }
            System.out.println("#ROWS\t" + p.getRowCount() + "\t" + p.getEncoding());
            Object[] row;
            while ((row = r.readNext()) != null) {
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < row.length; i++) {
                    if (i > 0) sb.append('\t');
                    sb.append(row[i] == null ? "" : row[i].toString());
                }
                System.out.println(sb);
            }
        }
    }
}
