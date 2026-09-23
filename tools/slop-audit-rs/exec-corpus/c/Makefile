CFLAGS ?=
LDFLAGS ?=

test: test_band
	./test_band

test_band: band.c test_band.c
	$(CC) $(CFLAGS) -o test_band band.c test_band.c $(LDFLAGS)

clean:
	rm -f test_band *.gcda *.gcno
