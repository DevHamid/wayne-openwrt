/* Fixed local AP locator read; no arbitrary QMI service or payload. */
#include <errno.h>
#include <limits.h>
#include <linux/qrtr.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static uint16_t le16(const unsigned char *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static uint32_t le32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static int validate_reply(const unsigned char *data, size_t size)
{
    static const char domain[] = "msm/modem/wlan_pd";
    size_t offset = 7, length;
    unsigned int seen = 0, bit;
    const unsigned char *value;
    if (size < 7 || data[0] != 2 || le16(data + 1) != 0x1234 ||
        le16(data + 3) != 0x21 || le16(data + 5) != size - 7)
        return -1;
    while (offset < size) {
        if (size - offset < 3)
            return -1;
        length = le16(data + offset + 1);
        value = data + offset + 3;
        if (length > size - offset - 3)
            return -1;
        switch (data[offset]) {
        case 2:
            bit = 1;
            if (length != 4 || le16(value) != 0 || le16(value + 2) != 0)
                return -1;
            break;
        case 16:
            bit = 2;
            if (length != 2 || le16(value) != 1)
                return -1;
            break;
        case 17:
            bit = 4;
            if (length != 2 || le16(value) != 1)
                return -1;
            break;
        case 18:
            bit = 8;
            if (length != 2 + sizeof(domain) - 1 + 9 || value[0] != 1 ||
                value[1] != sizeof(domain) - 1 ||
                memcmp(value + 2, domain, sizeof(domain) - 1) ||
                le32(value + 2 + sizeof(domain) - 1) != 180 ||
                value[2 + sizeof(domain) - 1 + 4] != 0 ||
                le32(value + 2 + sizeof(domain) - 1 + 5) != 0)
                return -1;
            break;
        default:
            return -1;
        }
        if (seen & bit)
            return -1;
        seen |= bit;
        offset += 3 + length;
    }
    return seen == 15 ? 0 : -1;
}

int main(int argc, char **argv)
{
    static const unsigned char request[] = {
        0, 0x34, 0x12, 0x21, 0, 10, 0,
        1, 7, 0, 'w', 'l', 'a', 'n', '/', 'f', 'w'
    };
    struct sockaddr_qrtr remote = { .sq_family = AF_QIPCRTR, .sq_node = 1 };
    struct sockaddr_qrtr peer = {0};
    struct pollfd pfd;
    unsigned char reply[512];
    unsigned long port;
    socklen_t peer_size = sizeof(peer);
    char *end;
    ssize_t size;
    int fd, rc = 1;

    if (argc != 2 || !argv[1][0] || argv[1][0] == '-')
        return 2;
    errno = 0;
    port = strtoul(argv[1], &end, 10);
    if (errno || *end || port == 0 || port >= 0xfffffffeUL)
        return 2;
    remote.sq_port = (uint32_t)port;
    fd = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
    if (fd < 0)
        return 1;
    size = sendto(fd, request, sizeof(request), 0,
                  (const struct sockaddr *)&remote, sizeof(remote));
    if (size != sizeof(request))
        goto out;
    pfd.fd = fd;
    pfd.events = POLLIN;
    pfd.revents = 0;
    if (poll(&pfd, 1, 2000) != 1 || !(pfd.revents & POLLIN) ||
        (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)))
        goto out;
    size = recvfrom(fd, reply, sizeof(reply), MSG_DONTWAIT | MSG_TRUNC,
                    (struct sockaddr *)&peer, &peer_size);
    if (size < 0 || (size_t)size > sizeof(reply) || peer_size != sizeof(peer) ||
        peer.sq_family != AF_QIPCRTR || peer.sq_node != 1 || peer.sq_port != remote.sq_port)
        goto out;
    if (validate_reply(reply, (size_t)size))
        goto out;
    rc = 0;
out:
    if (close(fd))
        rc = 1;
    if (rc == 0)
        puts("locator_reply=verified service=wlan/fw domain=msm/modem/wlan_pd instance=180");
    else
        fputs("locator_query=failed\n", stderr);
    return rc;
}
